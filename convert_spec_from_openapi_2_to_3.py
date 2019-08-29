import argparse
import json
from os.path import exists
import yaml

# Utility functions


def convert_definition_path(item):
    if '$ref' in item:
        item['$ref'] = item['$ref'].replace('/definitions/', '/components/schemas/')


def combine_description(item):
    if 'description' in item:
        item['description'] = item['description'].replace('\n', ' ')


def convert_property(prop):
    convert_definition_path(prop)
    if 'x-nullable' in prop:
        prop['nullable'] = prop['x-nullable']
        del(prop['x-nullable'])
    if 'items' in prop:
        convert_definition_path(prop['items'])
    if 'properties' in prop:
        for sub_prop in prop['properties'].values():
            convert_property(sub_prop)


def convert_definition(path, def_ob, verbose):
    if verbose:
        print(f"Looking at definition {path}")
    if 'type' in def_ob or '$ref' in def_ob:
        convert_property(def_ob)
    if 'properties' in def_ob:
        for prop_name, prop_ob in def_ob['properties'].items():
            convert_property(prop_ob)
    # Combiners using allOf, oneOf, anyOf, not:
    for comb in ('allOf', 'oneOf', 'anyOf', 'not'):
        for sub_def in def_ob.get(comb, []):
            print(f"... converting definition {sub_def}")
            convert_definition(path + '.' + comb, sub_def, verbose)
    if 'items' in def_ob:
        convert_definition(path + '.items', def_ob['items'])


def convert_parameter(param, verbose):
    if verbose:
        print(f"... convert parameter {param['name']} {'has' if 'schema' in param else 'no'} schema")
    convert_definition_path(param)
    combine_description(param)
    if 'schema' in param:
        convert_definition_path(param['schema'])
        if 'items' in param['schema']:
            convert_definition_path(param['schema']['items'])
    if 'in' in param and param['in'] not in ('query', 'header', 'path', 'cookie'):
        if verbose:
            print(f"!!! param {param['name']} in {param['in']}, changed to 'query'")
        param['in'] = 'query'
    if 'type' in param:
        if 'schema' not in param:
            param['schema'] = {}
        param['schema']['type'] = param['type']
        del(param['type'])
        # Straight conversions to schema:
        for field in ('format', 'pattern', 'default', 'enum'):
            if field in param:
                param['schema'][field] = param[field]
                del(param[field])
        if 'collectionFormat' in param:
            # Handle arrays by items key below
            del(param['collectionFormat'])
        if 'items' in param:
            param['style'] = 'simple'
            param['schema']['items'] = param['items']
            del(param['items'])
            convert_definition_path(param['schema']['items'])
        if 'aliases' in param:
            if verbose:
                print(f"!!! Discarding aliases {param['aliases']} for {param['name']}")
            del(param['aliases'])


def convert_parameters(item, verbose):
    if 'parameters' in item:
        for param in item['parameters']:
            convert_parameter(param, verbose)


def convert_responses(item, verbose, produces_list):
    if 'responses' in item:
        for resp_code, response in item['responses'].items():
            if verbose:
                print(f"... response {resp_code} = {response}")
            if 'schema' not in response:
                continue
            if (
                'schema' in response and  # noqa
                'properties' in response['schema']  # noqa
            ):
                for prop_name, prop_data in response['schema']['properties'].items():
                    convert_property(prop_data)
            elif 'schema' in response:
                convert_definition_path(response['schema'])
                if 'items' in response['schema']:
                    convert_definition_path(response['schema']['items'])
            # Move response schema into content:
            response['content'] = {
                produces: {
                    'schema': response['schema'],
                }
                for produces in produces_list
            }
            if 'headers' in response:
                for header, head_ob in response['headers'].items():
                    convert_parameter(head_ob, verbose)
            del(response['schema'])


def convert_schema(api, verbose=False, request=None):
    # Structure checks
    assert 'info' in api
    assert isinstance(api['info'], dict)
    assert 'paths' in api
    assert isinstance(api['paths'], dict)
    assert 'definitions' in api
    assert isinstance(api['definitions'], dict)

    # Make changes

    # Update version
    if 'swagger' in api:
        del(api['swagger'])
    if 'openapi' not in api:
        api['openapi'] = '3.0.0'

    # Convert host to server
    scheme = 'https'
    if request is not None and hasattr(request, 'scheme'):
        scheme = request.scheme
    base_path = api.get('basePath', '/')
    description = api['info'].get('description', 'No server description given')
    if 'host' in api:
        host_list = api['host'] if isinstance(api['host'], list) else [api['host']]
        del(api['host'])
        # Could use server variables here?
        hosts = [
            {
                'url': f"{scheme}://{host}{base_path}",
                'description': description,
            }
            for host in host_list
        ]
        del(api['basePath'])
        api['servers'] = hosts

    # Convert path information

    produces = api.get('produces', ['application/json'])

    for path, path_ob in api['paths'].items():
        assert isinstance(path_ob, dict)
        convert_parameters(path_ob, verbose)
        for op_name, op_ob in path_ob.items():
            if verbose:
                print(f"Path {path} op {op_name}")
            op_produces = produces
            if 'produces' in op_ob:
                op_produces = op_ob.pop('produces')
            if 'consumes' in op_ob:
                del(op_ob['consumes'])
            convert_parameters(op_ob, verbose)
            convert_responses(op_ob, verbose, op_produces)
            combine_description(op_ob)

    # Convert definitions into components

    for def_name, def_ob in api['definitions'].items():
        convert_definition(def_name, def_ob, verbose)

    api['components'] = {
        'schemas': api['definitions']
    }
    del(api['definitions'])

    # security section remains unchanged

    # Unneeded keys:

    for key in ('consumes', 'produces', 'schemes', 'securityDefinitions'):
        if key in api:
            del(api[key])

    return api

# file suffix -> read(handle) function, write(data, handle) function
format_functions = {
    '.json': {'load': json.load, 'dump': json.dump},
    '.yaml': {'load': yaml.full_load, 'dump': yaml.dump},
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Convert a spec file from OpenAPI 2 to 3"
    )

    parser.add_argument(
        'input_file',
        help='Input file'
    )
    parser.add_argument(
        'output_file',
        help='Output file'
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true', default=False,
        help='Show debugging information',
    )
    args = parser.parse_args()
    if not exists(args.input_file):
        print(f"ERROR: {args.input_file} not found")
        exit(1)
    for param, fname in (('input', args.input_file,), ('output', args.output_file,)):
        for ext, format_function in format_functions.items()
            if fname.endswith(ext):
                break
        else:
            print(f"ERROR: I don't know how to decode {param} file '{fname}'")
            print(f"I recognise these extensions: {', '.join(sorted(formatters.keys()))}")
            exit(1)

    # Load version 2

    ifh = open(args.input_file, 'r')
    api = format_function['load'](ifh)

    # Convert schema

    api3 = convert_schema(api, args.verbose)

    # Save version 3

    ofh = open(args.output_file, 'w')
    format_function['dump'](api3, ofh)
