#!/usr/bin/env python

import argparse
from xml.dom import minidom


TYPE_MAPPING = {
    'xs:int': 'VInt',
    'xs:long': 'VInt',
    'xs:boolean': 'VBool',
    'xs:string': 'VString',
    'xs:unsignedInt': 'VUnsignedInt',
    'xs:dateTime': 'VDateTime',
    'xs:time': 'VTime',
}
UNKNOWN = 'V???'



def element_to_kwarg(arg_attrs):
    optional = bool(arg_attrs.get('nillable'))
    typename = arg_attrs['type']
    vtype = TYPE_MAPPING.get(typename, UNKNOWN)
    name = arg_attrs['name']
    kwargs = []
    if optional:
        kwargs.append('required=False')
    if typename.startswith('tns:'):
        model_name = typename.split(':', 1)[1]
        vtype = 'VValidatorDict'
        kwargs.append('validator={}.validator'.format(model_name))
    return '{name}={vtype}({kwargs})'.format(name=name, vtype=vtype, kwargs=', '.join(sorted(kwargs)))



def get_attrs_from_complex_type(complex_type):
    elements = complex_type.getElementsByTagName('xs:element')
    yield from get_attrs_from_elements(elements)


def get_attrs_from_elements(elements):
    yield from ({k: v for k, v in element.attributes.items()} for element in elements)


def printable_validator(name, args_attrs):
    attr_lines = ['    {},'.format(element_to_kwarg(attrs)) for attrs in args_attrs]
    return '\n'.join([
        '# Type: {}'.format(name),
        'Validator(',
        *attr_lines,
        ')',
    ])


def get_complex_types_for_files(files):
    for path in files:
        with open(path) as xml_file:
            xml = minidom.parseString(xml_file.read())
        yield from xml.getElementsByTagName('xs:complexType')


def get_validators(files):
    for complex_type in get_complex_types_for_files(files):
        try:
            name = complex_type.attributes['name'].value
        except KeyError:
            name = complex_type.parentNode.attributes['name'].value
        args_attrs = get_attrs_from_complex_type(complex_type)
        yield printable_validator(name, args_attrs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='+')

    args = parser.parse_args()

    for validator in get_validators(args.files):
        print(validator)


if __name__ == '__main__':
    main()
