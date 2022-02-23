import boto3
import argparse
import re
import json

from collections import OrderedDict
from botocore.exceptions import ClientError

org_client = boto3.client('organizations')

def list_detectors(client, aws_region):
    """
    Lists the detectors in a given Account/Region
    Used to detect if a detector exists already
    :param client: GuardDuty client
    :param aws_region: AWS Region
    :return: Dictionary of AWS_Region: DetectorId
    """

    detector_dict = client.list_detectors()

    if detector_dict['DetectorIds']:
        for detector in detector_dict['DetectorIds']:
            detector_dict.update({aws_region: detector})

    else:
        detector_dict.update({aws_region: ''})

    return detector_dict

if __name__ == '__main__':

    # Setup command line arguments
    parser = argparse.ArgumentParser(description='Link AWS Accounts to central GuardDuty Account')
    parser.add_argument('--master_account', type=str, required=True, help="AccountId for Central AWS Account")
    parser.add_argument('--enabled_regions', type=str, help="comma separated list of regions to enable GuardDuty. If not specified, all available regions enabled")
    args = parser.parse_args()

    # Validate master accountId
    if not re.match(r'[0-9]{12}', args.master_account):
        raise ValueError("Master AccountId is not valid")

    # Getting GuardDuty regions
    session = boto3.session.Session()

    guardduty_regions = []
    if args.enabled_regions:
        guardduty_regions = [str(item) for item in args.enabled_regions.split(',')]
        print("Enabling members in these regions: {}".format(guardduty_regions))
    else:
        guardduty_regions = session.get_available_regions('guardduty')
        print("Enabling members in all available GuardDuty regions {}".format(guardduty_regions))

    master_detector_id_dict = dict()

    for aws_region in guardduty_regions:
        try:
            gd_client = boto3.client('guardduty', region_name=aws_region)
            detector_dict = list_detectors(gd_client, aws_region)

            if detector_dict[aws_region]:
                # a detector exists
                print('Found existing detector {detector} in {region} for account {account}'.format(
                    detector=detector_dict[aws_region],
                    region=aws_region,
                    account=args.master_account
                ))

                master_detector_id_dict.update({aws_region: detector_dict[aws_region]})

            else:

                print('No detectors found in {region} for account {account}, will create a new dectector to enable GuardDuty in this region'.format(
                    region=aws_region,
                    account=args.master_account
                ))

                # create a detector
                detector_str = gd_client.create_detector(Enable=True)['DetectorId']
                print('Created detector {detector} in {region} for {account}'.format(
                    detector=detector_str,
                        region=aws_region,
                        account=args.master_account
                    ))

                detector_dict.update({aws_region: detector_str})
                master_detector_id_dict.update({aws_region: detector_dict[aws_region]})

            master_detector=detector_dict[aws_region]

            response = gd_client.list_organization_admin_accounts()

            if response['AdminAccounts']:
                for account in response['AdminAccounts']:
                    print('Found GuardDuty delegated administrator account {account} in {region}'.format(
                        account=account['AdminAccountId'],
                        region=aws_region
                    ))
            else:
                response = gd_client.enable_organization_admin_account(
                    AdminAccountId=args.master_account
                )
                print('Enabled GuardDuty delegated administrator account {account} in {region}'.format(
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
                response = gd_client.create_members(
                    DetectorId=detector_dict[aws_region],
                    AccountDetails=accountDetails
                )
                if response['UnprocessedAccounts']:
                    for account in response['UnprocessedAccounts']:
                        print('The member account {account} in {region} was not processed: {reason}'.format(
                            account=account['AccountId'],
                            region=aws_region,
                            reason=account['Result']
                        ))
                else:
                    print('Member accounts created for detector {detector} in {region}'.format(
                        detector=detector_dict[aws_region],
                        region=aws_region,
                    ))
            else:
                print('No accounts found in organization of master account {account} in {region}'.format(
                    account=args.master_account,
                    region=aws_region
                ))
            
            response = gd_client.update_organization_configuration(
                DetectorId=detector_dict[aws_region],
                AutoEnable=True
            )

            print('Enabled GuardDuty (detector:: {detector}) automatically member accounts in the organization for master account {account} in {region}'.format(
                detector=detector_dict[aws_region],
                account=args.master_account,
                region=aws_region
            ))

        except ClientError as err:
            print('Error code: {code}, Error message: {message}'.format(
                    code=err.response['ResponseMetadata']['HTTPStatusCode'],
                    message=err.response['Error']['Message']
                ))