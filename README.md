# OpenAPI 2 to 3 converter

This is a tool to convert from OpenAPI 2 (Swagger) to OpenAPI 3 format.

The Swagger and OpenAPI 3 schemas are - unsurprisingly - reasonably similar.
Therefore, this tool basically tries to massage the former into the latter,
applying as much force as necessary.  It has only a basic understanding of
the actual meaning of what it's changing, so it is not guaranteed to work on
all valid Swagger 2 specs, or generate a completely coherent and valid
OpenAPI 3 spec.

It has been tested using the output of Django's REST Framework and 'drf-yasg'
Swagger schema generation tools.  When the Swagger 2 spec passes the
'openapi-spec-validator' package's `validate_v2_spec` schema validation, the
converted output passes that package's `validate_v3_spec` schema validation.

# License

This code is licensed under the GNU GPL v3, because I look forward to
getting lots of improvements to its conversions :-)

# Usage

## Command line

This can be either used as a command-line utility:

```sh
$ convert_spec_from_openapi_2_to_3.py --help
usage: convert_spec_from_openapi_2_to_3.py [-h] [-v] input_file output_file

Convert a spec file from OpenAPI 2 to 3

positional arguments:
  input_file     Input file
  output_file    Output file

optional arguments:
  -h, --help     show this help message and exit
  -v, --verbose  Show debugging information

$ convert_spec_from_openapi_2_to_3.py swagger_spec.json openapi_3_spec.yaml
```

Both input and output can be in either `JSON` or `YAML` formats, as specified
by their file suffix.

## In Code

This can also be used in your code to convert the schema on the fly:

```python
# Swagger views:
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.views import get_schema_view
from api.scripts.convert_spec_from_openapi_2_to_3 import convert_schema

v1info = openapi.Info(
    title="Project API",
    default_version='v1',
    description="An API for working with this project",
)


class OpenAPI3SchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, request, public):
        schema = super(OpenAPI3SchemaGenerator, self).get_schema(request, public)
        return convert_schema(schema, request=request)


openapi3_view = get_schema_view(
    v1info,
    public=True,
    permission_classes=(AllowAny,),
    generator_class=OpenAPI3SchemaGenerator,
)

#
```
