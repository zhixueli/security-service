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
    parser.add_argument('--disable_master', action="store_true", help="indicate if disable GuardDuty service for master account")
    args = parser.parse_args()

    # Validate master accountId
    if not re.match(r'[0-9]{12}', args.master_account):
        raise ValueError("Master AccountId is not valid")

    # Getting GuardDuty regions
    session = boto3.session.Session()

    guardduty_regions = []
    if args.enabled_regions:
        guardduty_regions = [str(item) for item in args.enabled_regions.split(',')]
        print("Disabling members in these regions: {}".format(guardduty_regions))
    else:
        guardduty_regions = session.get_available_regions('guardduty')
        print("Disabling members in all available GuardDuty regions {}".format(guardduty_regions))

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

                print('No detectors found in {region} for account {account}'.format(
                    region=aws_region,
                    account=args.master_account
                ))

            master_detector=detector_dict[aws_region]

            response = gd_client.list_members(
                DetectorId=detector_dict[aws_region],
                OnlyAssociated='true'
            )

            member_accounts = [member['AccountId'] for member in response['Members']]

            if member_accounts:
                print('Found member accounts for detector {detector} in {region}: {accounts}'.format(
                    detector=detector_dict[aws_region],
                    region=aws_region,
                    accounts=member_accounts
                ))

                response = gd_client.disassociate_members(
                    DetectorId=detector_dict[aws_region],
                    AccountIds=member_accounts
                )

                if response['UnprocessedAccounts']:
                    for account in response['UnprocessedAccounts']:
                        print('The member account {account} in {region} was not processed: {reason}'.format(
                            account=account['AccountId'],
                            region=aws_region,
                            reason=account['Result']
                        ))
                else:
                    print('Member accounts disabled for detector {detector} in {region}: {accounts}'.format(
                    detector=detector_dict[aws_region],
                    region=aws_region,
                    accounts=member_accounts
                ))
            else:
                print('No member accounts found for detector {detector} in {region}'.format(
                    detector=detector_dict[aws_region],
                    region=aws_region
                ))

            response = gd_client.list_organization_admin_accounts()
            if response['AdminAccounts']:
                response = gd_client.disable_organization_admin_account(
                    AdminAccountId=args.master_account
                )

                print('Disabled master account {account} in {region} as the GuardDuty delegated administrator'.format(
                    account=args.master_account,
                    region=aws_region
                ))

            if args.disable_master:
                response = gd_client.delete_detector(
                    DetectorId=detector_dict[aws_region]
                )
                print('Disabled GuardDuty service (detector:: {detector}) for master account {account} in {region}'.format(
                    detector=detector_dict[aws_region],
                    account=args.master_account,
                    region=aws_region
                ))

        except ClientError as err:
            print('Error code: {code}, Error message: {message}'.format(
                    code=err.response['ResponseMetadata']['HTTPStatusCode'],
                    message=err.response['Error']['Message']
                ))