import yaml
import boto3

# Please copy your AWS Access key ID below.
ACCESS_KEY = ""

# Please copy your AWS Secret Access key below.
SECRET_KEY = ""

# Please copy your AWS Session Token below (optional).
SESSION_TOKEN = ""

# Please mention your AWS region name below.
REGION_NAME = ""

# Connecting to Boto3 client.
client = boto3.client("ec2", aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY,
                      aws_session_token=SESSION_TOKEN,
                      region_name=REGION_NAME)

resource = boto3.resource("ec2", aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY,
                      aws_session_token=SESSION_TOKEN,
                      region_name=REGION_NAME)

iam = boto3.client("iam", aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY,
                      aws_session_token=SESSION_TOKEN,
                      region_name=REGION_NAME)

# Creating a key for an instance with the below name.
key_name = "FetchRewardsEC2"


# Loading YAML configuration file.
def load_configuration():
    try:
        print("Loading YAML configuration file")
        with open("configuration.yaml", "rt") as file:
            config = yaml.safe_load(file)

        return config

    except Exception as e:
        print(e)
        return


# Parsing all the variables out of the configuration file.
def get_ec2_parameters(config):
    user_names, vol_devices, vol_sizes = [], [], []
    try:
        print("Parsing values from configuration file.")
        instance_type = config['server']['instance_type']
        architecture = config['server']['architecture']
        root_device_type = config['server']['root_device_type']
        virtualization_type = config['server']['virtualization_type']
        min_count = config['server']['min_count']
        max_count = config['server']['max_count']
        users = config['server']['users']
        for user in users:
            user_names.append(user['login'])

        volumes = config['server']['volumes']
        for volume in volumes:
            vol_devices.append(volume['device'])
            vol_sizes.append(volume['size_gb'])

        return instance_type, architecture, root_device_type, virtualization_type, user_names, min_count, max_count, \
            vol_devices, vol_sizes

    except Exception as e:
        print(e)
        return


# Find all the available EC2 instances that match our requirements.
def find_instances(instance_type, architecture, root_device_type, virtualization_type):
    try:
        print("Fetching available EC2 instances.")
        instances = client.describe_instances(
            Filters=[
                {
                    'Name': 'architecture',
                    'Values': [architecture]
                },
                {
                    'Name': 'root-device-type',
                    'Values': [root_device_type]
                },
                {
                    'Name': 'virtualization-type',
                    'Values':
                        [virtualization_type]
                },
                {
                    'Name': 'instance-type',
                    'Values': [instance_type]
                }
            ],
        )
        image_id_instance = instances['Reservations'][0]['Instances'][0]['ImageId']
        print("Found image ID instance: ", image_id_instance)
        return image_id_instance

    except Exception as e:
        print(e)


# Creating the required key value pair for running an instance.
def create_key_pair():
    try:
        print("Creating Key Pair with Name: ", key_name)
        keypair_response = client.create_key_pair(
            KeyName=key_name
        )
        print(keypair_response)
    except Exception as e:
        print(e)


# Create users with full access to EC2 instances
def create_user(user_names):
    try:
        for user in user_names:
            print("Creating user with Name: ", user)
            response = iam.create_user(UserName=user)
            print("Granting programmatic access to user with Name: ", user)
            iam.create_access_key(UserName=user)
            print("Grating Full Access to EC2 instance to user name: ", user)
            response = client.attach_user_policy(
                PolicyArn='arn:aws:iam::aws:policy/AmazonEC2FullAccess',
                UserName=user,
            )

    except Exception as e:
        print(e)


mountCode = """#!/bin/bash
sudo mkfs.ext4 /dev/xvdf
sudo mkdir /data
echo "/dev/xvdf /data auto noatime 0 0" | sudo tee -a /etc/fstab"""


# Create instance with image ID.
def create_instance(image_id, instance_type, min_count, max_count):
    try:
        print("Creating EC2 instance")
        new_reservation = client.run_instances(ImageId=image_id, InstanceType=instance_type, KeyName=key_name,
                                               MinCount=min_count, MaxCount=max_count, UserData=mountCode,
                                               BlockDeviceMappings=[{"DeviceName": "/dev/xvda", "Ebs": {"VolumeSize": 10}}])

        instance_id = new_reservation['Instances'][0]['InstanceId']
        availability_zone = new_reservation['Instances'][0]['Placement']['AvailabilityZone']

        # Waiter Initialization
        waiter = client.get_waiter('instance_running')
        print("Please wait for the instance to be up and running.")

        waiter.wait(InstanceIds=[instance_id])

        print("The instance is up.")
        return instance_id, availability_zone
    except Exception as e:
        print(e)


# Create volumes to be attached to the instance
def create_volume(availability_zone, vol_sizes):
    volume_id = None
    try:

        response2 = client.create_volume(AvailabilityZone=availability_zone, Encrypted=False, Size=vol_sizes[1])
        if response2['ResponseMetadata']['HTTPStatusCode'] == 200:
            volume_id = response2['VolumeId']
            print("Volume ID2: ", volume_id)

            print("Please wait until volume2 is created.")
            client.get_waiter('volume_available').wait(VolumeIds=[volume_id])
            print("Success. Volume 2 :", volume_id, "was created.")

        if volume_id is not None:
            return volume_id
        else:
            print("Could not create volumes.")
            return

    except Exception as e:
        print(e)


# Detach any existing volumes on the instance
def detach_existing_volumes(instance_id, vol_devices):
    try:
        instance = resource.Instance(instance_id)
        volumes = instance.volumes.all()
        print(volumes)
        for volume in volumes:
            print("Detaching existing volumes on device: ", volume.id,
                  " from instance: ", instance_id)
            response1 = client.detach_volume(Device=vol_devices[0], InstanceId=instance_id, VolumeId=volume.id)

    except Exception as e:
        print(e)


# Attach volumes to instance
def attach_volume(instance_id, volume_id2, vol_devices):
    try:
        print("Attaching volume: ", volume_id2, "to: ", instance_id)
        response = client.attach_volume(Device=vol_devices[1], InstanceId=instance_id, VolumeId=volume_id2)
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            client.get_waiter('volume_in_use').wait(VolumeIds=[volume_id2])
            print("Success. Volume: ", volume_id2, "is attached to instance: ", instance_id)

    except Exception as e:
        print(e)


# Step 1: Load the YAML configuration file.
data = load_configuration()

# Step 2: Parse the configuration values.
instanceType, architectureType, rootDeviceType, virtualizationType, userNames, minCount, maxCount, \
    volDevices, volSizes = get_ec2_parameters(data)

# Step 3: Find all the available instances matching our requirements and get the imageIDInstance of each
imageIDInstance = find_instances(instanceType, architectureType, rootDeviceType, virtualizationType)

# Step 4: Create key pair having access to the instance.
create_key_pair()

# Step 5: Create users to access the instance with full Amazon EC2 Access.
create_user(userNames)

# Step 5: Run the instance found earlier.
instanceId, availabilityZone = create_instance(imageIDInstance, instanceType, minCount, maxCount)

# Step 6: Create volumes
volume_2 = create_volume(availabilityZone, volSizes)

# Step 7: Attach the volumes created at Step 6 to instance
attach_volume(instanceId, volume_2, volDevices)
