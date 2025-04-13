import boto3  
import logging  
import sys  
from botocore.exceptions import ClientError  
from datetime import datetime  
import time

# Set up logging  
logging.basicConfig(  
    level=logging.INFO,  
    format='%(asctime)s - %(levelname)s - %(message)s',  
    handlers=[  
        logging.StreamHandler(sys.stdout),  
        logging.FileHandler("vpc_deletion.log")  
    ]  
)  
logger = logging.getLogger()

# Function to fetch AWS profiles  
def fetch_aws_profiles():  
    session = boto3.Session()  
    return session.available_profiles

# Function to fetch available regions for a profile  
def fetch_regions(profile):  
    session = boto3.Session(profile_name=profile)  
    ec2 = session.client('ec2')  
      
    try:  
        # Fetch all regions using describe_regions API call  
        regions = ec2.describe_regions()  
        return [region['RegionName'] for region in regions['Regions']]  
    except ClientError as e:  
        logger.error(f"Error fetching regions for profile {profile}: {e}")  
        return []

# Function to collect default VPCs across all regions  
def collect_default_vpcs(profile, regions):  
    default_vpcs = {}

    for region in regions:  
        session = boto3.Session(profile_name=profile, region_name=region)  
        ec2 = session.client('ec2')  
        logger.info(f"Checking for default VPC in region {region}...")

        try:  
            response = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])  
            if response['Vpcs']:  
                vpc_id = response['Vpcs'][0]['VpcId']  
                default_vpcs[region] = vpc_id  
            else:  
                logger.info(f"No default VPC found in region {region}.")  
        except ClientError as e:  
            logger.error(f"Error in region {region}: {e}")

    return default_vpcs

# Function to delete default VPCs with retry mechanism  
def delete_default_vpcs(profile, default_vpcs):  
    for region, vpc_id in default_vpcs.items():  
        session = boto3.Session(profile_name=profile, region_name=region)  
        ec2 = session.client('ec2')

        try:  
            # Deleting VPC with retries in case of transient errors  
            logger.info(f"Attempting to delete default VPC {vpc_id} in region {region}...")  
            ec2.delete_vpc(VpcId=vpc_id)  
            logger.info(f"Successfully deleted VPC {vpc_id} in region {region}.")  
        except ClientError as e:  
            logger.error(f"Failed to delete VPC {vpc_id} in region {region}: {e}")  
            # Retry logic for transient errors  
            retries = 3  
            for attempt in range(retries):  
                time.sleep(5)  
                try:  
                    ec2.delete_vpc(VpcId=vpc_id)  
                    logger.info(f"Successfully deleted VPC {vpc_id} in region {region} after retry.")  
                    break  
                except ClientError as retry_error:  
                    logger.error(f"Retry {attempt + 1} failed for VPC {vpc_id} in region {region}: {retry_error}")  
                    if attempt == retries - 1:  
                        logger.error(f"Max retries reached for VPC {vpc_id} in region {region}.")

# Function to handle the user confirmation for deletion  
def confirm_deletion(default_vpcs):  
    print("nThe following default VPCs will be deleted:")  
    for region, vpc_id in default_vpcs.items():  
        print(f"Region: {region}, VPC ID: {vpc_id}")

    confirm = input("nDo you want to proceed with the deletion of these VPCs? (yes/no): ").strip().lower()

    if confirm != 'yes':  
        logger.info("Aborted deletion process.")  
        return False  
    return True

# Main function  
def main():  
    try:  
        # Fetch profiles and prompt user to select one  
        profiles = fetch_aws_profiles()  
        if not profiles:  
            logger.error("No AWS profiles found.")  
            return

        print("Available AWS profiles:")  
        for i, profile in enumerate(profiles, start=1):  
            print(f"{i}. {profile}")  
          
        profile_choice = int(input("Choose an AWS profile (by number): "))  
        profile = profiles[profile_choice - 1]

        # Fetch regions for the selected profile  
        regions = fetch_regions(profile)  
        if not regions:  
            logger.error(f"No regions found for profile {profile}.")  
            return

        # Collect default VPCs in all regions  
        default_vpcs = collect_default_vpcs(profile, regions)

        if not default_vpcs:  
            logger.info("No default VPCs found across all regions.")  
            return

        # Confirm before deletion  
        if confirm_deletion(default_vpcs):  
            delete_default_vpcs(profile, default_vpcs)  
            logger.info("All selected default VPCs have been deleted successfully.")  
        else:  
            logger.info("No default VPCs were deleted. Exiting script.")

    except Exception as e:  
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":  
    main()

