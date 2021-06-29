# pythonAWSAutomation

This is an automation program that consumes a YAML configuration file and deploys a Linux AWS EC2 instance. The current configuration that I am working with has two volumes and two users. The program has been coded in Python and Boto3 module. This is my first attempt at AWS so please let me know of any improvements!

Here are some guidelines to follow to run this program:

1. Please input your AWS Access Key ID, AWS Secret Access Key, AWS Session Token (if exists) and Region Name from your AWS Management Console.
2. If you're starting fresh, you would need to create a new user in AWS Management Console giving programmatic rights to the user. That would get you a new set of keys.
3. If you modify the existing configuration, there would be some changes required to ingest the YAML file.
4. At the end of the program, you would have a new instance up and running with two volumes attached to it and two new users created having access to that instance.
