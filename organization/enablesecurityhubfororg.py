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
    args = parser.parse_args()

    # Validate master accountId
    if not re.match(r'[0-9]{12}', args.master_account):
        raise ValueError("Master AccountId is not valid")

    # Getting SecurityHub regions
    session = boto3.session.Session()

    securityhub_regions = []
    if args.enabled_regions:
        securityhub_regions = [str(item) for item in args.enabled_regions.split(',')]
        print("Enabling members in these regions: {}".format(securityhub_regions))
    else:
        securityhub_regions = session.get_available_regions('guardduty')
        print("Enabling members in all available SecurityHub regions {}".format(securityhub_regions))

    for aws_region in securityhub_regions:
        try:
            sh_client = boto3.client('securityhub', region_name=aws_region)

            if is_securityhub_enabled(sh_client):
                print('Master account {account} is already subscribed to SecurityHub in {region}'.format(
                    account=args.master_account,
                    region=aws_region
                ))
            else:    
                response = sh_client.enable_security_hub(
                    EnableDefaultStandards=True
                )
                print('SecurityHub is enabled for master account {account} in {region}'.format(
                    account=args.master_account,
                    region=aws_region
                ))

            response = sh_client.list_organization_admin_accounts()

            if response['AdminAccounts']:
                for account in response['AdminAccounts']:
                    print('Found SecurityHub delegated administrator account {account} in {region}'.format(
                        account=account['AccountId'],
                        region=aws_region
                    ))
            else:
                response = sh_client.enable_organization_admin_account(
                    AdminAccountId=args.master_account
                )
                print('Enabled SecurityHub delegated administrator account {account} in {region}'.format(
                    account=args.master_account,
                    region=aws_region
                ))

            response = org_client.list_accounts()
            accountDetails=[]

            if response['Accounts']:
                for account in response['Accounts']:
                    if account['Id'] != args.master_account:
                        memberAccount = {
                            'AccountId': account['Id'],
                            'Email': account['Email']
                        }
                        accountDetails.append(memberAccount)

            if accountDetails:
                print('Accounts found in organization of master account {account} in {region}: {accounts}'.format(
                    account=args.master_account,
                    region=aws_region,
                    accounts=accountDetails
                ))
                response = sh_client.create_members(
                    AccountDetails=accountDetails
                )
                if response['UnprocessedAccounts']:
                    for account in response['UnprocessedAccounts']:
                        print('The member account {account} in {region} was not processed: {reason}'.format(
                            account=account['AccountId'],
                            region=aws_region,
                            reason=account['ProcessingResult']
                        ))
                else:
                    print('Member accounts created for master account {account} in {region}'.format(
                        account=args.master_account,
                        region=aws_region,
                    ))
            else:
                print('No accounts found in organization of master account {account} in {region}'.format(
                    account=args.master_account,
                    region=aws_region
                ))

            response = sh_client.update_organization_configuration(
                AutoEnable=True
            )

            print('Enabled SecurityHub automatically member accounts in the organization for master account {account} in {region}'.format(
                account=args.master_account,
                region=aws_region
            ))

        except ClientError as err:
            print('Error code: {code}, Error message: {message}'.format(
                    code=err.response['ResponseMetadata']['HTTPStatusCode'],
                    message=err.response['Error']['Message']
                ))

    # Enabling finding aggregation only for master region
    try:

        sh_client = boto3.client('securityhub', region_name=args.master_region)
        response = sh_client.list_finding_aggregators()

        if response['FindingAggregators']:
            for aggregator in response['FindingAggregators']:
                    print('Found aggregator {aggregator} for master account {account} in master region {region}'.format(
                        aggregator=aggregator['FindingAggregatorArn'],
                        account=args.master_account,
                        region=args.master_region
                    ))
        else:
            response = sh_client.create_finding_aggregator(
                RegionLinkingMode='ALL_REGIONS'
            )
            print('Enabled finding aggregation for master account {account} in master region {region} to aggregate findings from all regions'.format(
                account=args.master_account,
                region=args.master_region
            ))
    
    except ClientError as err:
        print('Error code: {code}, Error message: {message}'.format(
                code=err.response['ResponseMetadata']['HTTPStatusCode'],
                message=err.response['Error']['Message']
            ))