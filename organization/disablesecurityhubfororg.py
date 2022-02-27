import boto3
import argparse
import re
import json

from collections import OrderedDict
from botocore.exceptions import ClientError

org_client = boto3.client('organizations')

def is_securityhub_enabled(client):
    """
    Check if SecurityHub enbaled in a given Account/Region
    :param client: SecurityHub client
    :param aws_region: AWS Region
    :return: True/False
    """

    try:
        response = client.describe_hub()

        if response['HubArn']:
            return True
        else:
            return False

    except ClientError as err:
        if err.response['Error']['Code'] == 'InvalidAccessException':
            return False

if __name__ == '__main__':

    # Setup command line arguments
    parser = argparse.ArgumentParser(description='Link AWS Accounts to central GuardDuty Account')
    parser.add_argument('--master_account', type=str, required=True, help="AccountId for Central AWS Account")
    parser.add_argument('--master_region', type=str, required=True, help="Region that you want to use as the aggregation Region.")
    parser.add_argument('--enabled_regions', type=str, help="comma separated list of regions to enable SecurityHub. If not specified, all available regions enabled")
    parser.add_argument('--disable_master', action="store_true", help="indicate if disable SecurityHub service for master account")
    args = parser.parse_args()

    # Validate master accountId
    if not re.match(r'[0-9]{12}', args.master_account):
        raise ValueError("Master AccountId is not valid")

    # Getting SecurityHub regions
    session = boto3.session.Session()

    securityhub_regions = []
    if args.enabled_regions:
        securityhub_regions = [str(item) for item in args.enabled_regions.split(',')]
        print("Disabling members in these regions: {}".format(securityhub_regions))
    else:
        securityhub_regions = session.get_available_regions('guardduty')
        print("Disabling members in all available SecurityHub regions {}".format(securityhub_regions))

    # Disabling finding aggregation for master region
    try:

        sh_client = boto3.client('securityhub', region_name=args.master_region)

        if is_securityhub_enabled(sh_client):

                response = sh_client.list_finding_aggregators()

                if response['FindingAggregators']:
                    for aggregator in response['FindingAggregators']:
                        print('Found aggregator {aggregator} for master account {account} in master region {region}'.format(
                            aggregator=aggregator['FindingAggregatorArn'],
                            account=args.master_account,
                            region=args.master_region
                        ))

                        response = sh_client.delete_finding_aggregator(
                            FindingAggregatorArn=aggregator['FindingAggregatorArn']
                        )

                        print('Disabled finding aggregation for master account {account} in master region {region}'.format(
                            account=args.master_account,
                            region=args.master_region
                        ))
                else:
                    print('No finding aggregation found for master account {account} in master region {region}'.format(
                        account=args.master_account,
                        region=args.master_region
                    ))
        else:    
            print('SecurityHub is not enabled for master account {account} in master region {region}'.format(
                account=args.master_account,
                region=args.master_region
            ))
    
    except ClientError as err:
        print('Error code: {code}, Error message: {message}'.format(
                code=err.response['ResponseMetadata']['HTTPStatusCode'],
                message=err.response['Error']['Message']
            ))

    for aws_region in securityhub_regions:
        try:
            sh_client = boto3.client('securityhub', region_name=aws_region)

            if is_securityhub_enabled(sh_client):
                
                response = sh_client.list_members(
                    OnlyAssociated=True
                )

                member_accounts = [member['AccountId'] for member in response['Members']]

                if member_accounts:
                    print('Found member accounts for master account {account} in {region}: {accounts}'.format(
                        account=args.master_account,
                        region=aws_region,
                        accounts=member_accounts
                    ))

                    response = sh_client.disassociate_members(
                        AccountIds=member_accounts
                    )
                    
                    print('Member accounts disassociated from master acount {account} in {region}: {accounts}'.format(
                        account=args.master_account,
                        region=aws_region,
                        accounts=member_accounts
                    ))

                else:
                    print('No member accounts found for master acount {account} in {region}'.format(
                        account=args.master_account,
                        region=aws_region
                    ))

                response = sh_client.list_organization_admin_accounts()

                if response['AdminAccounts']:
                    response = sh_client.disable_organization_admin_account(
                        AdminAccountId=args.master_account
                    )

                    print('Disabled master account {account} in {region} as the SecurityHub delegated administrator'.format(
                        account=args.master_account,
                        region=aws_region
                    ))

                if args.disable_master:
                    response = sh_client.disable_security_hub()

                    print('Disabled SecurityHub service for master account {account} in {region}'.format(
                        account=args.master_account,
                        region=aws_region
                    ))

            else:
                print('SecurityHub is not enabled for master account {account} in {region}'.format(
                    account=args.master_account,
                    region=aws_region
                ))

        except ClientError as err:
            print('Error code: {code}, Error message: {message}'.format(
                    code=err.response['ResponseMetadata']['HTTPStatusCode'],
                    message=err.response['Error']['Message']
                ))
    

    