import subprocess
import json
import csv
import re

# Create a list to store all Labels of instances
vm_labels = ['application-name', 'automation-trigger', 'backup-policy', 'billingcode', 'businessowner', 'client', 'contactgroup', 'country', 'cs', 'cstype', 'environment', 'function', 'goog-dm', 'hostname', 'intended-environment', 'memberfirm', 'msp', 'patch-group', 'primarycontact', 'projectid', 'projectname', 'resource-severity', 'resourcegroup', 'resourcetype', 'secondarycontact', 'sid', 'solution-name', 'vnedormanaged']

# Get a list of all projects under the organization
projects = subprocess.check_output(['gcloud', 'projects', 'list', '--format=json'])
#project_list=['ca-con-gcp-prd-mel0001-092321', 'ca-con-gcp-npr-mel0001-092321', 'ca-con-gcp-svc-mel0001-092321']

projects_json = json.loads(projects)

# Create a list to store all VM instances
vm_instances = []

# Loop through each project and get a list of VM instances
for project in projects_json:
    project_id = project['projectId']

    # Run the gcloud command to list VM instances for the project and capture the output
    vm_list = subprocess.check_output(['gcloud', 'compute', 'instances', 'list', '--project', project_id, '--format=json'])

    # Create a list to store all unique labels
    labels = set()
    
    # Parse the output as JSON
    vm_list_json = json.loads(vm_list)
    
    # Append each VM instance to the list
    for vm in vm_list_json:
        creation_time = vm['creationTimestamp'].split('T')[0]
        tags = ', '.join(vm['tags']['items']) if 'items' in vm['tags'] else ''
        subnetwork = vm['networkInterfaces'][0]['subnetwork'].split('/')[-1] if len(vm['networkInterfaces']) > 0 and 'subnetwork' in vm['networkInterfaces'][0] else ''
        private_ip = vm['networkInterfaces'][0]['networkIP'] if len(vm['networkInterfaces']) > 0 else ''
        
        #Get OS name
        license_url = vm['disks'][0]['licenses'][0]
        os_name = license_url.split("/")[-1]
        
        status = vm['status']
        
        # Exclude instances with TERMINATED or STOPPED status
        if status in ['TERMINATED', 'STOPPED']:
            continue

        # Define the command to be executed
        command = f"gcloud compute ssh {vm['name']} --zone {vm['zone'].split('/')[-1]} --project {project_id} --tunnel-through-iap --command 'systemctl is-active collector'"

        try:

            # Execute the command and capture the output
            output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)

            # Decode the output to UTF-8 encoding
            output = output.decode('utf-8').strip()

            # Extract the status of the collector
            sumo = output.split()[-1]

        except subprocess.CalledProcessError as e:
            if e.returncode == 3:
                sumo = 'Inactive'

        # Run command and capture output
        command = f"gcloud compute instances os-inventory describe {vm['name']} --zone {vm['zone'].split('/')[-1]} --project {project_id} | grep 'Kernel'"
        try:

            result = subprocess.run(command, stdout=subprocess.PIPE, shell=True, check=True)
            output = result.stdout.decode().strip()

            # Extract kernel version
            kernel_version = output.split('\n')[0].split(': ')[1]
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                kernel_version = 'Unavailable'

        #check all the services
        all_services_status = {}
        w_all_services_status = {}        

        # Define the services to check status
        services = ['stackdriver-agent', 'collector', 'google-fluentd', 'traps_pmd.service']
        
        if re.search(r'windows.*server.*2019.*dc', os_name, re.IGNORECASE):

            win_service_name = ['StackdriverMonitoring', 'sumo-collector',  'StackdriverLogging', 'cyserver']
            for wservice in win_service_name:
                command = f"gcloud compute ssh  {vm['name']} --zone {vm['zone'].split('/')[-1]} --project {project_id} --tunnel-through-iap --command 'sc query {wservice} | find \"STATE\" | find /i \"RUNNING\" > nul && echo active'"        

                try:
                    # Run the command to check the service status remotely using PowerShell
                    output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
    
                    # Decode the output from bytes to string
                    status = output.decode('utf-8').strip()

                    w_all_services_status[wservice] = status.split()[-1]   
                    print(w_all_services_status[wservice])   
                except subprocess.CalledProcessError as e:
                    if e.returncode == 3:
                        w_all_services_status[wservice] = 'Inactive'
                    else:
                        w_all_services_status[wservice] = 'Inactive'
            # Print the status of all services
            for service, status in w_all_services_status.items():
                print(f" {vm['name']} - {wservice}: {status}")


        else:
    
            for service in services:
                # Define the command to be executed
                command = f"gcloud compute ssh {vm['name']} --zone {vm['zone'].split('/')[-1]} --project {project_id} --tunnel-through-iap --command 'systemctl is-active {service}'"

                try:       
                    # Execute the command and capture the output
                    output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)

                    # Decode the output from bytes to string
                    status = output.decode('utf-8').strip()

                    # Add the service status to the dictionary
                    all_services_status[service] = status.split()[-1]
                except subprocess.CalledProcessError as e:
                        if e.returncode == 3:
                            all_services_status[service] = 'Inactive'
                        else:
                            all_services_status[service] = 'N/A'

            # Print the status of all services
            for service, status in all_services_status.items():
                print(f" {vm['name']} - {service}: {status}")

        # Exit from the ssh connection
        subprocess.run('exit', shell=True)

        if re.search(r'windows.*server.*2019.*dc', os_name, re.IGNORECASE):

            vm_instance = [
                project_id,
                vm['name'],
                str(vm['id']),
                kernel_version,
                status,
                creation_time,
                vm['zone'].split('/')[-1],
                vm['machineType'].split('/')[-1],
                tags,
                subnetwork,
                private_ip,
                os_name,
                w_all_services_status['StackdriverMonitoring'],
                w_all_services_status['sumo-collector'],
                w_all_services_status['StackdriverLogging'],
                w_all_services_status['cyserver']
            ]
        else:
                vm_instance = [
                project_id,
                vm['name'],
                str(vm['id']),
                kernel_version,
                status,
                creation_time,
                vm['zone'].split('/')[-1],
                vm['machineType'].split('/')[-1],
                tags,
                subnetwork,
                private_ip,
                os_name,
                all_services_status['stackdriver-agent'],
                all_services_status['collector'],
                all_services_status['google-fluentd'],
                all_services_status['traps_pmd.service']
            ]

        # Loop through each label for the VM instance
        if 'labels' in vm and vm['labels']:
            for label in vm['labels']:
                # Add the label to the set of unique labels
                labels.add(label)
                # Append the label value as a separate column to the VM instance
                vm_instance.append(vm['labels'][label])
        else:
            # Add "Missing" as the value for each unique label for the VM instance
            for label in vm['labels']:
                vm_instance.append("Missing")

        vm_instances.append(vm_instance)

# Create a CSV file and write the header row and VM instances
header = ['Project ID', 'VM Name', 'Instance ID', 'kernel_version', 'Status', 'Creation Time', 'Zone', 'Machine Type', 'Tags','Subnetwork', 'Private IP', 'OS Name', 'Stackdriver-agent', 'SumoLogic', 'Logging-agent', 'XDR']

for i in range(len(vm_labels)):

    header.append(vm_labels[i])

with open('vm_inventory.csv', 'w', newline='') as csv_file:
    writer = csv.writer(csv_file)
    writer.writerow(header)

    for vm_instance in vm_instances:
        writer.writerow(vm_instance)
