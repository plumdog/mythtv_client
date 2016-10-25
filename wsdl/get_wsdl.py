#!/usr/bin/env python

import sys
import os
import argparse
import requests
from xml.dom import minidom
from urllib.parse import urlunparse, urlparse, parse_qs

SERVICES = [
    'capture',
    'channel',
    'content',
    'dvr',
    'frontend',
    'guide',
    'myth',
    'video',
]

SCHEME = 'http'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--domain', help='target domain name that hosts MythTV', default='localhost')
    parser.add_argument('-p', '--port', type=int, default=6544)
    parser.add_argument('-t', '--types', action='store_const', const=True, default=False)
    services = parser.add_mutually_exclusive_group(required=True)
    services.add_argument('-s', '--services', nargs='+', choices=SERVICES, help='target service')
    services.add_argument('-a', '--all', action='store_const', dest='services', const=SERVICES)

    args = parser.parse_args()

    found_types = set()
    for service in args.services:
        try:
            wsdl = get_wsdl_for_service(args.domain, args.port, service)
        except Exception as exc:
            print(exc, file=sys.stderr)
            continue

        path = '{service}.xml'.format(service=service)
        write_xml(wsdl, path)

        if args.types:
            if not os.path.exists('types'):
                os.makedirs('types')

            xmls = get_types(wsdl, found_types)

            for name, type_xml in xmls.items():
                path = 'types/{name}.xml'.format(name=name)
                write_xml(type_xml, path)


def write_xml(xml, path):
    content = tidy_wsdl(xml)
    with open(path, 'w') as file_xml:
        file_xml.write(content)


def get_wsdl_for_service(domain, port, service):
    path = '{service}/wsdl'.format(service=service.capitalize())
    loc = '{domain}:{port}'.format(domain=domain, port=port)
    url = urlunparse((SCHEME, loc, path, None, None,  None))
    return get_xml_for_url(url)


def get_xml_for_url(url):
    response = requests.get(url)
    response.raise_for_status()
    return minidom.parseString(response.content.decode())


def tidy_wsdl(xml):
    lines = xml.toprettyxml().splitlines()
    stripped_lines = [l.rstrip() for l in lines]
    cleared_lines = filter(None, stripped_lines)
    return '\n'.join(cleared_lines) + '\n'


def get_types(xml, found_types):
    """Get the dict of names to xml objects for the types specified at the
    top of the given wsdl xml. Eg:

    <xs:schema targetNamespace="http://MythTV.org/Imports">
        <xs:import namespace="http://mythtv.org" schemaLocation="http://localhost:6544/Capture/xsd?type=CaptureCard"/>
        ...

    """
    type_imports = xml.getElementsByTagName('xs:import') + xml.getElementsByTagName('xs:include')
    type_urls = [t.attributes['schemaLocation'].value for t in type_imports]

    def type_from_url(type_url):
        query_dict = parse_qs(urlparse(type_url).query)
        if 'type' not in query_dict:
            print('Cannot process for {}'.format(type_url))
            return
        return query_dict['type'][0]

    urls_parsed = {type_url: type_from_url(type_url) for type_url in type_urls}
    urls_parsed = {k: v for k, v in urls_parsed.items() if v}

    types = {}
    for url, type_ in urls_parsed.items():
        if type_ in found_types:
            # Type has already been found and processed
            continue

        try:
            type_xml = get_xml_for_url(url)
        except Exception as exc:
            print(exc, file=sys.stderr)
        else:
            found_types.add(type_)
            types[type_] = type_xml
            types.update(get_types(type_xml, found_types))

    return types


if __name__ == '__main__':
    main()
