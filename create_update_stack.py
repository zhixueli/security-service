'Update or create a stack given a name and template + params'
from __future__ import division, print_function, unicode_literals

from datetime import datetime
import logging
import json
import sys
import argparse

import boto3
import botocore

import utils

cf = boto3.client('cloudformation')  
log = logging.getLogger('deploy.cf.create_or_update') 

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError("Type not serializable")

if __name__ == '__main__':

    # Setup command line arguments
    parser = argparse.ArgumentParser(description='Create or Update Stack')
    parser.add_argument('--name', type=str, required=True, help="Stackset Name")
    parser.add_argument('--template', type=str, required=True, help='Path to Cloudformation template file')
    parser.add_argument('--parameters', type=str, help='Path to parameters json file')
    args = parser.parse_args()
    
    # Update or create stack
    template_data = utils.parse_template(args.template)
    if args.parameters != None:
        parameter_data = utils.parse_parameters(args.parameters)
        params = {
            'StackName': args.name,
            'TemplateBody': template_data,
            'Parameters': parameter_data,
            'Capabilities': ['CAPABILITY_NAMED_IAM'],
        }
    else:
        params = {
            'StackName': args.name,
            'TemplateBody': template_data,
            'Capabilities': ['CAPABILITY_NAMED_IAM'],
        }

    try:
        if utils.stack_exists(args.name):
            print('Updating {}'.format(args.name))
            stack_result = cf.update_stack(**params)
            waiter = cf.get_waiter('stack_update_complete')
        else:
            print('Creating {}'.format(args.name))
            stack_result = cf.create_stack(**params)
            waiter = cf.get_waiter('stack_create_complete')
        print("...waiting for stack to be ready...")
        waiter.wait(StackName=args.name)
    except botocore.exceptions.ClientError as ex:
        error_message = ex.response['Error']['Message']
        if error_message == 'No updates are to be performed.':
            print("No changes")
        else:
            raise
    else:
        print(json.dumps(
            cf.describe_stacks(StackName=stack_result['StackId']),
            indent=2,
            default=json_serial
        ))