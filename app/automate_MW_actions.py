import os
import re
import json
import time
import requests
import datetime
import cx_Oracle
import pandas as pd

# ----------------------------------------------------------------------
# Define directories here! (remember a / on the end of the path buddy):
# ----------------------------------------------------------------------
# input_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/exports_dir/'
# output_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/output_dir/'
# archive_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/archive_dir/'

input_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/CSV - Need to Process/'
output_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/exports/'
archive_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/archive_dir/'

credentials_path = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/credentials.json'
# ----------------------------------------------------------------------


def fetch_UUIDs_from_csv(file_list):

    final_UUID_dict = {}

    for filename in file_list:
    
        if filename[0] == "~":
            continue
        # print(filename)

        df1 = pd.read_excel(input_dir + filename, sheet_name = 'Sheet1')
        # print(df1)

        UUID_header_cell = []
        orderNo_header_cell = []
        valid_UUID_headings = ["UUID", "Z1RRUKEY"]
        valid_orderNo_headings = ["ERP Order #", "Order #", "Z1RRORNO"]

        for row in range(df1.shape[0]): # df1.shape is the entire dimensions of the spreadsheet. E.g. 3x19 (square around all cells with data in them)
            for col in range(df1.shape[1]):
                if df1.iloc[row, col] in valid_UUID_headings: # finding the column heading for the UUID column
                    # print("UUID HEADER CELL ---->", row, col)
                    UUID_header_cell += [row, col]
                elif str(df1.iloc[row, col]) in valid_orderNo_headings: # finding the column heading for the Order # column
                    # print("orderNo HEADER CELL ---->", row, col)
                    orderNo_header_cell += [row, col]
        
        # for i in the ROW value inside UUID_header_cell minus 1, iterate and print the row, col of only the 1 column we found under it. print the value with iloc.
        
        for i in range(df1.shape[0] - (UUID_header_cell[0]+1)):

            # print("cell we are looking up:", i+UUID_header_cell[0]+1, UUID_header_cell[1])
            current_uuid = df1.iloc[i+UUID_header_cell[0]+1, UUID_header_cell[1]]
            
            # print("cell we are looking up v2:", i+orderNo_header_cell[0]+1, orderNo_header_cell[1])
            current_orderNo = str(df1.iloc[i+orderNo_header_cell[0]+1, orderNo_header_cell[1]])

            final_UUID_dict[current_uuid] = current_orderNo
        
    # print("final_UUID_dict: ", final_UUID_dict)
    return final_UUID_dict


def get_audit_db_original_requests(UUIDs):

    ### Fetch database credentials:

    print("Fetching Database credentials from file...")

    if os.path.isfile(credentials_path):
        with open(credentials_path) as file:
            data = json.load(file)
            hostname = data['hostname']
            username = data['username']
            password = data['password']
            service_name = data['service_name']
            port = data['port']
            file.close()
            print("Credentials fetched!")
    else:
        print("credentials_path.json not found!")
        return False, "credentials_path.json not found!"

    ### Query Oracle db for audit logs:

    try:
        print("Querying middleware database...")
        conn_str = '{0}/{1}@{2}:{3}/{4}'.format(username, password, hostname, port, service_name)
        cx_Oracle.init_oracle_client("C:/dev/Program Files/instantclient_19_10/")
        con = cx_Oracle.connect(conn_str)
        cursor = con.cursor()

        total_records = len(UUIDs)
        # UUIDs = {"776606eb-67f3-4ac0-ba34-996e55d0e7b8": "4251138", "ef5980b7-eebb-4dfc-8d31-20239fd8dbef": "4251166"} # delete

        format_strings = ','.join(["'%s'"] * total_records) # creates template of comma separated %s that is n values long depending how many UUIDs we are searching
        sql = '''
        SELECT a.correlation_id,
        (select TO_CHAR(substr(b.payload,instr(b.payload,'erpOrderNumber>')+15 ,7)) from audit_log_details b where b.phase = 'FINAL' and b.STATE = 'FINISHED' and b.correlation_id = a.correlation_id) as ordernumber_Payload,
        (select c.payload from audit_log_details c where c.comments ='Create Sample Order Orchestration start process' and
        c.correlation_id=a.correlation_id and ROWNUM <= 1) as payload
        from audit_log_Details a where a.phase = 'WAIVENET' and a.STATE = 'ERROR'
        and a.correlation_id in (%s) order by a.correlation_id
        '''  % (format_strings) % tuple(UUIDs.keys())
        cursor.execute(sql)

        print("Database SELECT v1 performed successfully")

        successful_UUIDs_list = []
        failed_UUIDs = {}
        final_file = ""
        for row in cursor:
            # print("UUID: ", row[0], "\nOrderNo: ", row[1], "\nPayload: ", row[2], sep="")
            final_file += str(row[0]) + "," + str(row[1]) + "," + str(row[2]) + "\n"
            successful_UUIDs_list += [row[0]]

        print("final successful_UUIDs_list: ", successful_UUIDs_list) # delete
        # if UUiD is in OG list but not in successful_UUIDs_list, add it to failed_UUIDs (ALONG WITH ITS ORDERNO):

        if total_records == len(successful_UUIDs_list):
            print("final_file: ", final_file)
            return final_file
        else:
            for key in UUIDs:
                value = UUIDs[key]
                if key not in successful_UUIDs_list: # if the UUID was not successfully fetched in the first db query, add it to failed_UUIDs dict
                    failed_UUIDs[key] = value

        ### backup query if nothing was returned for one of the UUIDs:

        # change this to actual list of failed UUIDs:
        # failed_UUIDs = ['bd4cc1fc-81f7-4aa8-9172-98e30e56dd89', 'ef5980b7-eebb-4dfc-8d31-20239fd8dbef']
        # failed_UUIDs = {"bd4cc1fc-81f7-4aa8-9172-98e30e56dd89": "4223885", "ef5980b7-eebb-4dfc-8d31-20239fd8dbef": "4223890"}

        # could maybe just iterate the corresponding orderNo's at the final for loop printing the values below.

        format_strings = ','.join(["'%s'"] * len(failed_UUIDs)) # creates template of comma separated %s that is n values long depending how many UUIDs we are searching
        sql = '''
        SELECT correlation_id, payload FROM audit_log_details
        WHERE STATE = 'START' and PHASE = 'CREATESAMPLORDR-ORCH'
        and correlation_id in (%s) order by correlation_id
        '''  % format_strings % tuple(failed_UUIDs.keys())
        cursor.execute(sql)

        count = 0
        values_list = list(failed_UUIDs.values())
        for row in cursor:
            print("UUID: ", row[0], "\nOrderNo: ", values_list[count], "\nPayload: ", row[1], sep="")
            final_file += str(row[0]) + "," + str(values_list[count]) + "," + str(row[1]) + "\n"
            count += 1

        print("Database SELECT v2 performed successfully")
        print("final_file: ", final_file)
        return final_file

    except cx_Oracle.DatabaseError as e:
        print("\nERROR in Oracle Database Query:\n\n", e, "\n", sep="")
        return None

    finally: # closing db connection (found this is very important!)
        if cursor:
            cursor.close()
        if con:
            con.close()


def list_files_in_input_dir():
    # get a list of all filenames currently inside the unprocessed export.csv directory.
    print("Fetching list of CSV files to be processed...")

    file_list = os.listdir(input_dir)
    print("Found {} files!".format(len(file_list)))
    return file_list


def transform_exports_csv(filename):

    # for each file found inside list_files_in_input_dir, transform its contents to the necessary output file.
    print("Reading contents of file --> {}".format(filename))

    try:
        if os.path.isfile(input_dir + filename):
            with open(input_dir + filename) as file:
                contents = file.read()
                file.close()

                ### removing first line "CORRELATION_ID,ORDERNUMBER_PAYLOAD,PAYLOAD" from file contents:
                removed_first_line = contents.replace("CORRELATION_ID,ORDERNUMBER_PAYLOAD,PAYLOAD", "")
                print("Removed first line: CORRELATION_ID,ORDERNUMBER_PAYLOAD,PAYLOAD!")

                ### removing all line feeds and carrage returns from file:
                removed_line_endings = removed_first_line.replace("\n", "")

                ### replacing soap body opening and closing tags + adding newline char onto closing tag:
                opening_current = '<soap-env:Body xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://fbu.com/CommonServices/GenericAuditService">'
                opening_new = '<soapenv:Body xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:lam="http://fbu.com/BuildingProducts/LaminexEcomSampleProductOrchestrator" xmlns:com="http://fbu.com/common">'
                replaced_openings = removed_line_endings.replace(opening_current, opening_new)
                print("Replaced soap body openings!")

                closing_current = '</soap-env:Body>'
                closing_new ='</soapenv:Body>\n'
                replaced_closings = replaced_openings.replace(closing_current, closing_new)
                print("Replaced soap body closings!")

                ### Looping each line in file (Checking Phone, Postcode, and extra Commas):

                # --------------------------
                # Test Lines:
                # --------------------------
                # replaced_closings = 'hello, there, my, name, is, cole'    # line for testing extra commas
                line = 'this is a test line <ns2:postalCode>3427</ns2:postalCode> where their <ns2:phone>0407445979x</ns2:phone>are many <ns2:postalCode>cole</ns2:postalCode> values, and<ns2:phoneNumber/> this <ns2:postalCode/> sne<ns2:phoneNumber>yeet</ns2:phoneNumber>aky'
                # line = 'this is a test line <ns2:postalCode>3427</ns2:postalCode> where their are many <ns2:postalCode>cole</ns2:postalCode> values, and this <ns2:postalCode/> sneaky'
                # line = 'this is a string where the substring "<ns2:phone>0407445979x</ns2:phone>" is repeated several <ns2:phoneNumber>yeet</ns2:phoneNumber> times'
                # line = 'this is a string where the substring "<ns2:phone/>" is repeated several <ns2:phoneNumber/>yeet</ns2:phoneNumber> times'
                # --------------------------

                yes_list = ['yes', 'ya', 'yep', 'yes pls', 'yas', 'ye', 'y', 'yes!']
                no_list = ['no', 'n', 'nah', 'na', 'nope', 'no thanks']
                final_removed_commas = ""
                line_num = 1
                for line in replaced_closings.splitlines():

                    ### Checking for valid phone numbers:

                    # for each instance we find "<ns2:phone" in the line:
                    phone_offset = 0

                    for a in list(re.finditer('<ns2:phone', line)):

                        # If we find an empty phone field, do nothing, otherwise fetch the value + its indexes from inbetween the tags:
                        if line[a.start()-phone_offset:a.start()+12-phone_offset] == "<ns2:phone/>":
                            print("empty phone found, skipping") # delete

                        elif line[a.start()-phone_offset:a.start()+18-phone_offset] == "<ns2:phoneNumber/>":
                            print("empty phoneNumber found, skipping") # delete

                        else:
                            print("line preview: ", line[a.start()-phone_offset:a.start()+35-phone_offset])

                            rest_of_line = line[a.start()-phone_offset+1:] # the + 1 removes first < from very start
                            value_opening_index = rest_of_line.find(">")
                            value_closing_index = rest_of_line.find("<")
                            original_opening_index = a.start()-phone_offset + value_opening_index + 2
                            original_closing_index = a.start()-phone_offset + value_closing_index + 1

                            if (value_opening_index != -1) and (value_closing_index != -1):
                                phone_value = rest_of_line[value_opening_index+1:value_closing_index]
                            else:
                                error_msg = "Invalid closing and opening >'s found when looking at <ns2:phone!!! very bad!"
                                raise Exception(error_msg)

                            if phone_value.isdigit(): # if it contains all numbers, its fine, let it slide
                                print("valid phone number found, letting it past")
                                pass
                            else: # else, has some invalid characters, then we do the following:
                                print("Invalid phone number found:\n--->", phone_value, "<---", sep="")

                                current_value_length = len(phone_value)
                                final_phone_value = ''
                                valid = False
                                while not valid:
                                    requested_phone_value = input("what you want to change this field to buddy?: ")
                                    if len(requested_phone_value) > 0:
                                        print("Are you sure you want to change the <ns2:phone field to:\n--->", requested_phone_value, "<---", sep="")
                                        confirmation = input("yes/no: ")
                                        if (confirmation in yes_list) and requested_phone_value.isdigit():
                                            final_phone_value = requested_phone_value
                                            new_value_length = len(requested_phone_value)
                                            phone_offset = current_value_length - new_value_length + phone_offset
                                            valid = True
                                        elif (confirmation in yes_list) and requested_phone_value.isdigit() == False:
                                            print("Invalid phone number entered sorry, has to be numbers only.")
                                        elif confirmation in no_list:
                                            pass # takes us back to another while loop iteration asking for new input.
                                    else:
                                        confirmation = input("no input given! are you sure you want no value in this field? yes/no: ")
                                        if confirmation in yes_list:
                                            final_phone_value = '' # set final_phone_value as blank
                                            new_value_length = len(requested_phone_value)
                                            phone_offset = current_value_length - new_value_length + phone_offset
                                            valid = True
                                        elif confirmation in no_list:
                                            pass # takes us back to another while loop iteration asking for new input.

                                line = line[0:original_opening_index] + final_phone_value + line[original_closing_index:]
                                print("FULL new_line: ", line)

                    ### Checking for valid postcodes:

                    # for each instance we find "<ns2:post" in the line:
                    postcode_offset = 0

                    for a in list(re.finditer('<ns2:post', line)):

                        # If we find an empty postcode field, do nothing, otherwise fetch the value + its indexes from inbetween the tags:
                        if line[a.start()-postcode_offset:a.start()+17-postcode_offset] == "<ns2:postalCode/>":
                            print("empty postcode found, skipping") # delete
                        else:
                            print("line preview: ", line[a.start()-postcode_offset:a.start()+35-postcode_offset])

                            rest_of_line = line[a.start()-postcode_offset+1:] # the + 1 removes first < from very start
                            value_opening_index = rest_of_line.find(">")
                            value_closing_index = rest_of_line.find("<")
                            original_opening_index = a.start()-postcode_offset + value_opening_index + 2
                            original_closing_index = a.start()-postcode_offset + value_closing_index + 1

                            if (value_opening_index != -1) and (value_closing_index != -1):
                                postcode_value = rest_of_line[value_opening_index+1:value_closing_index]
                            else:
                                error_msg = "Invalid closing and opening >'s found when looking at <ns2:post!!! very bad!"
                                raise Exception(error_msg)

                            if postcode_value.isdigit(): # if it contains all numbers, its fine, let it slide
                                print("valid postcode found, letting it past")
                                pass
                            else: # else, has some invalid characters, then we do the following:
                                print("Invalid postcode found:\n--->", postcode_value, "<---", sep="")

                                current_value_length = len(postcode_value)
                                postcode_value = ''
                                valid = False
                                while not valid:
                                    postcode_value = input("what you want to change this field to buddy?: ")
                                    if len(postcode_value) > 0:
                                        print("Are you sure you want to change the <ns2:post field to:\n--->", postcode_value, "<---", sep="")
                                        confirmation = input("yes/no: ")
                                        if (confirmation in yes_list) and postcode_value.isdigit():
                                            postcode_value = postcode_value
                                            new_value_length = len(postcode_value)
                                            postcode_offset = current_value_length - new_value_length + postcode_offset
                                            valid = True
                                        elif (confirmation in yes_list) and postcode_value.isdigit() == False:
                                            print("Invalid postcode entered sorry, has to be numbers only.")
                                        elif confirmation in no_list:
                                            pass # takes us back to another while loop iteration asking for new input.
                                    else:
                                        confirmation = input("no input given! are you sure you want no value in this field? yes/no: ")
                                        if confirmation in yes_list:
                                            # if the value i entered is fully blank, need to replace the line with <ns2:post/>... or i guess <ns2:postalCode></ns2:postalCode> would work
                                            postcode_value = '' # set postcode_value as blank
                                            new_value_length = len(postcode_value)
                                            postcode_offset = current_value_length - new_value_length + postcode_offset
                                            valid = True
                                        elif confirmation in no_list:
                                            pass # takes us back to another while loop iteration asking for new input.

                                line = line[0:original_opening_index] + postcode_value + line[original_closing_index:]
                                print("FULL new_line: ", line) # delete


                    ### checking for extra commas which break the request separators. should only have 2 per line:

                    comma_count = line.count(",")
                    if comma_count <= 2:
                        final_removed_commas += line + "\n"
                    else:
                        print("\nExtra commas found in line_number {} !".format(line_num))
                        print("Number of extra commas --> {}".format(comma_count-2))
                        split_line = line.split(",")
                        removed_commas = ""
                        for i in range(len(split_line)):
                            if i < 2:
                                removed_commas += (split_line[i] + ",")
                            else:
                                removed_commas += split_line[i]
                        final_removed_commas += removed_commas + "\n"
                        # print("\ncommas were found in this part of the line:\n\n", ",".join(split_line[0:len(split_line)]), sep="")
                        print("Commas were found in this part of the line:\n\n", split_line[len(split_line)-2], ",", split_line[len(split_line)-1][0:20], "\n", sep="")
                    line_num += 1


                # ### write file contents to output file in output_dir:

                now = datetime.datetime.now()
                export_file_name = now.strftime("export_%Y%m%d_%H%M%S%f.csv")

                with open(output_dir + export_file_name, 'w') as file:
                    file.write(final_removed_commas)
                    file.close()

                ### move successfully transformed file to archive_dir:
                os.replace(input_dir + filename, archive_dir + filename)

        else:
            print("Could not find file with name --> {}".format(filename))
            return None

    except Exception as e:
        print("------------------------------------------------------")
        print("Error while transforming csv file:\n", e)
        print("------------------------------------------------------")


def transform_exports_csv_v2(contents):
    try:
        ### removing all line feeds and carrage returns from file:
        # removed_line_endings = removed_first_line.replace("\n", "")
        removed_line_endings = contents.replace("\n", "")

        ### replacing soap body opening and closing tags + adding newline char onto closing tag:
        opening_current = '<soap-env:Body xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://fbu.com/CommonServices/GenericAuditService">'
        opening_new = '<soapenv:Body xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:lam="http://fbu.com/BuildingProducts/LaminexEcomSampleProductOrchestrator" xmlns:com="http://fbu.com/common">'
        replaced_openings = removed_line_endings.replace(opening_current, opening_new)
        print("Replaced soap body openings!")

        closing_current = '</soap-env:Body>'
        closing_new ='</soapenv:Body>\n'
        replaced_closings = replaced_openings.replace(closing_current, closing_new)
        print("Replaced soap body closings!")

        ### Looping each line in file (Checking Phone, Postcode, and extra Commas):

        # --------------------------
        # Test Lines:
        # --------------------------
        # replaced_closings = 'hello, there, my, name, is, cole'    # line for testing extra commas
        line = 'this is a test line <ns2:postalCode>3427</ns2:postalCode> where their <ns2:phone>0407445979x</ns2:phone>are many <ns2:postalCode>cole</ns2:postalCode> values, and<ns2:phoneNumber/> this <ns2:postalCode/> sne<ns2:phoneNumber>yeet</ns2:phoneNumber>aky'
        # line = 'this is a test line <ns2:postalCode>3427</ns2:postalCode> where their are many <ns2:postalCode>cole</ns2:postalCode> values, and this <ns2:postalCode/> sneaky'
        # line = 'this is a string where the substring "<ns2:phone>0407445979x</ns2:phone>" is repeated several <ns2:phoneNumber>yeet</ns2:phoneNumber> times'
        # line = 'this is a string where the substring "<ns2:phone/>" is repeated several <ns2:phoneNumber/>yeet</ns2:phoneNumber> times'
        # --------------------------

        yes_list = ['yes', 'ya', 'yep', 'yes pls', 'yas', 'ye', 'y', 'yes!']
        no_list = ['no', 'n', 'nah', 'na', 'nope', 'no thanks']
        final_removed_commas = ""
        final_line_list = []
        line_num = 1
        for line in replaced_closings.splitlines():

            ### Checking for valid phone numbers:

            # for each instance we find "<ns2:phone" in the line:
            phone_offset = 0

            for a in list(re.finditer('<ns2:phone', line)):

                # If we find an empty phone field, do nothing, otherwise fetch the value + its indexes from inbetween the tags:
                if line[a.start()-phone_offset:a.start()+12-phone_offset] == "<ns2:phone/>":
                    print("empty phone found, skipping") # delete

                elif line[a.start()-phone_offset:a.start()+18-phone_offset] == "<ns2:phoneNumber/>":
                    print("empty phoneNumber found, skipping") # delete

                else:
                    rest_of_line = line[a.start()-phone_offset+1:] # the + 1 removes first < from very start
                    value_opening_index = rest_of_line.find(">")
                    value_closing_index = rest_of_line.find("<")
                    original_opening_index = a.start()-phone_offset + value_opening_index + 2
                    original_closing_index = a.start()-phone_offset + value_closing_index + 1

                    if (value_opening_index != -1) and (value_closing_index != -1):
                        phone_value = rest_of_line[value_opening_index+1:value_closing_index]
                    else:
                        error_msg = "Invalid closing and opening >'s found when looking at <ns2:phone!!! very bad!"
                        raise Exception(error_msg)

                    if phone_value.isdigit(): # if it contains all numbers, its fine, let it slide
                        pass
                    else: # else, has some invalid characters, then we do the following:
                        print("Invalid phone number found:\n--->", phone_value, "<---", sep="")

                        current_value_length = len(phone_value)
                        final_phone_value = ''
                        valid = False
                        while not valid:
                            requested_phone_value = input("what you want to change this field to buddy?: ")
                            if len(requested_phone_value) > 0:
                                print("Are you sure you want to change the <ns2:phone field to:\n--->", requested_phone_value, "<---", sep="")
                                confirmation = input("yes/no: ")
                                if (confirmation in yes_list) and requested_phone_value.isdigit():
                                    final_phone_value = requested_phone_value
                                    new_value_length = len(requested_phone_value)
                                    phone_offset = current_value_length - new_value_length + phone_offset
                                    valid = True
                                elif (confirmation in yes_list) and requested_phone_value.isdigit() == False:
                                    print("Invalid phone number entered sorry, has to be numbers only.")
                                elif confirmation in no_list:
                                    pass # takes us back to another while loop iteration asking for new input.
                            else:
                                confirmation = input("no input given! are you sure you want no value in this field? yes/no: ")
                                if confirmation in yes_list:
                                    final_phone_value = '' # set final_phone_value as blank
                                    new_value_length = len(requested_phone_value)
                                    phone_offset = current_value_length - new_value_length + phone_offset
                                    valid = True
                                elif confirmation in no_list:
                                    pass # takes us back to another while loop iteration asking for new input.

                        line = line[0:original_opening_index] + final_phone_value + line[original_closing_index:]
                        print("FULL new_line: ", line)

            ### Checking for valid postcodes:

            # for each instance we find "<ns2:post" in the line:
            postcode_offset = 0

            for a in list(re.finditer('<ns2:post', line)):

                # If we find an empty postcode field, do nothing, otherwise fetch the value + its indexes from inbetween the tags:
                if line[a.start()-postcode_offset:a.start()+17-postcode_offset] == "<ns2:postalCode/>":
                    print("empty postcode found, skipping") # delete
                else:
                    print("line preview: ", line[a.start()-postcode_offset:a.start()+35-postcode_offset])

                    rest_of_line = line[a.start()-postcode_offset+1:] # the + 1 removes first < from very start
                    value_opening_index = rest_of_line.find(">")
                    value_closing_index = rest_of_line.find("<")
                    original_opening_index = a.start()-postcode_offset + value_opening_index + 2
                    original_closing_index = a.start()-postcode_offset + value_closing_index + 1

                    if (value_opening_index != -1) and (value_closing_index != -1):
                        postcode_value = rest_of_line[value_opening_index+1:value_closing_index]
                    else:
                        error_msg = "Invalid closing and opening >'s found when looking at <ns2:post!!! very bad!"
                        raise Exception(error_msg)

                    if postcode_value.isdigit(): # if it contains all numbers, its fine, let it slide
                        print("valid postcode found, letting it past")
                        pass
                    else: # else, has some invalid characters, then we do the following:
                        print("Invalid postcode found:\n--->", postcode_value, "<---", sep="")

                        current_value_length = len(postcode_value)
                        postcode_value = ''
                        valid = False
                        while not valid:
                            postcode_value = input("what you want to change this field to buddy?: ")
                            if len(postcode_value) > 0:
                                print("Are you sure you want to change the <ns2:post field to:\n--->", postcode_value, "<---", sep="")
                                confirmation = input("yes/no: ")
                                if (confirmation in yes_list) and postcode_value.isdigit():
                                    postcode_value = postcode_value
                                    new_value_length = len(postcode_value)
                                    postcode_offset = current_value_length - new_value_length + postcode_offset
                                    valid = True
                                elif (confirmation in yes_list) and postcode_value.isdigit() == False:
                                    print("Invalid postcode entered sorry, has to be numbers only.")
                                elif confirmation in no_list:
                                    pass # takes us back to another while loop iteration asking for new input.
                            else:
                                confirmation = input("no input given! are you sure you want no value in this field? yes/no: ")
                                if confirmation in yes_list:
                                    # if the value i entered is fully blank, need to replace the line with <ns2:post/>... or i guess <ns2:postalCode></ns2:postalCode> would work
                                    postcode_value = '' # set postcode_value as blank
                                    new_value_length = len(postcode_value)
                                    postcode_offset = current_value_length - new_value_length + postcode_offset
                                    valid = True
                                elif confirmation in no_list:
                                    pass # takes us back to another while loop iteration asking for new input.

                        line = line[0:original_opening_index] + postcode_value + line[original_closing_index:]
                        print("FULL new_line: ", line) # delete


            ### checking for extra commas which break the request separators. should only have 2 per line:

            comma_count = line.count(",")
            if comma_count <= 2:
                final_removed_commas += line + "\n"
                final_line_list += [line]
            else:
                print("\nExtra commas found in line_number {} !".format(line_num))
                print("Number of extra commas --> {}".format(comma_count-2))
                split_line = line.split(",")
                removed_commas = ""
                for i in range(len(split_line)):
                    if i < 2:
                        removed_commas += (split_line[i] + ",")
                    else:
                        removed_commas += split_line[i]
                final_removed_commas += removed_commas + "\n"
                final_line_list += [removed_commas]
                # print("\ncommas were found in this part of the line:\n\n", ",".join(split_line[0:len(split_line)]), sep="")
                print("Commas were found in this part of the line:\n\n", split_line[len(split_line)-2], ",", split_line[len(split_line)-1][0:20], "\n", sep="")
            line_num += 1


        # ### write file contents to output file in output_dir:

        now = datetime.datetime.now()
        export_file_name = now.strftime("export_%Y%m%d_%H%M%S%f.csv")

        with open(output_dir + export_file_name, 'w') as file:
            file.write(final_removed_commas)
            file.close()

        ### move successfully transformed file to archive_dir:
        file_list = os.listdir(input_dir)
        for filename in file_list:
            os.replace(input_dir + filename, archive_dir + filename)

        ## return final list of individual output file lines generated:
        return final_line_list

    except Exception as e:
        print("------------------------------------------------------")
        print("Error while transforming csv file:\n", e)
        print("------------------------------------------------------")


def post_to_ConverterProxy(payload_list, UUID_list):
    
    print("Fetching ConverterProxy API URL credentials from file...")

    if os.path.isfile(credentials_path):
        with open(credentials_path) as file:
            data = json.load(file)
            url = data['converterproxy_url']
            proxy_url = data['proxy_url']
            proxy_username = data['proxy_username']
            proxy_password = data['proxy_password']
            file.close()
            print("Credentials fetched!")
    else:
        print("Failed to send payload to ConverterProxy. credentials_path.json not found!")
        return

    UUID_keys = list(UUID_list.keys())

    headers = {
        "content-type": "application/text",
        "Connection": "keep-alive",
        # "User-Agent": "Apache-HttpClient/4.5.10 (Java/1.8.0_282)"
        }

    # http_proxy  = "http://124.248.141.10:80"

    proxyDict = { 
        "http" : "http://{}:{}@{}".format(proxy_username, proxy_password, proxy_url),
        "https" : "http://{}:{}@{}".format(proxy_username, proxy_password, proxy_url)
    }

    # proxyDict = { 
    #     "http" : "http://pac.zscalertwo.net/znhplmTTcVdl/fb-v1.pac",
    #     "https" : "http://pac.zscalertwo.net/znhplmTTcVdl/fb-v1.pac"
    # }

    
    # "https://user:password@proxyip:port"
    print("proxyDict: ", proxyDict)

    # Imitating the Apache JMeter for loop here, sending each post call out:

    for i in range(len(UUID_keys)):
        # print("UUID_keys[i] ", UUID_keys[i])
        if UUID_keys[i] in payload_list[i]:
            # print("payload_list[i]: ", payload_list[i])
            post_payload = UUID_list[UUID_keys[i]] + "#" + payload_list[i]

            r = requests.post(url, data = post_payload, headers=headers, proxies=proxyDict)
            resp = r.json()
            print("json response:", resp)

            time.sleep(2)


def main():
    print("------------------------------------------------------")
    print("Starting automate_MW_actions.py...")
    print("------------------------------------------------------")

    # fetch UUIDs of failed orders from email attachment CSV:
    # resp = fetch_UUIDs_from_csv()
    # # convert this to single line if statement:
    # if not(resp[0]):
    #     return
    # else:
    #     UUIDs = resp[1]
    #
    # # query audit database for the original requests of these orders:
    # resp = get_audit_db_original_requests(UUIDs)
    # if not(resp[0]):
    #     return

    # get list of all files inside the input_dir currently
    file_list = list_files_in_input_dir()
    UUID_list = fetch_UUIDs_from_csv(file_list)

    # UUID_list = {"776606eb-67f3-4ac0-ba34-996e55d0e7b8": "4251138", "625af53b-8ca3-4f52-9dd9-d801a780a1f3": "4251166"}
    # UUID_list = {"e18dbbd2-3c8f-47c5-bc5e-711cd9b5a8f8": "4272926"}

    contents = get_audit_db_original_requests(UUID_list)
    final_payload_list = transform_exports_csv_v2(contents)

    # # # UUID_list = {"74a780cb-3cb2-4c0c-b67f-54de8872ded6": "4287411", "84a780cb-3cb2-4c0c-b67f-54de8872ded6": "4287411"}
    # # # final_payload_list = ['74a780cb-3cb2-4c0c-b67f-54de8872ded6,4287411,<soapenv:Body xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:lam="http://fbu.com/BuildingProducts/LaminexEcomSampleProductOrchestrator" xmlns:com="http://fbu.com/common"><ns2:createOrderRequest xmlns:ns2="http://fbu.com/BuildingProducts/LaminexEcomSampleProductOrchestrator"><ns2:erpId>AU-1067063</ns2:erpId><ns2:leadId/><ns2:salesforceCompanyId>0010X00004Ry1jWQAR</ns2:salesforceCompanyId><ns2:userId>0030X00002T9uJiQAJ</ns2:userId><ns2:userName>janetgrahaminteriors@gmail.com</ns2:userName><ns2:orderNo/><ns2:phoneNumber/><ns2:orderTotal>0.0</ns2:orderTotal><ns2:optIn/><ns2:processId>ef6ab9fb-bb75-480c-8a94-3169f917cc80</ns2:processId><ns2:relatedProjectInformation>Mosman home+Residential Renovation</ns2:relatedProjectInformation><ns2:creationTime>2021-03-30T12:57:57.211GMT+11</ns2:creationTime><ns2:order><ns2:line><ns2:lineNumber>1</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM4507-GLS-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>2</ns2:orderQty><ns2:description>Milano Venato Gloss</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Gloss</ns2:finish><ns2:color>Milano Venato</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line><ns2:line><ns2:lineNumber>2</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM0489-GLS-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>1</ns2:orderQty><ns2:description>Pure Cloud</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Gloss</ns2:finish><ns2:color>Pure Cloud</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line><ns2:line><ns2:lineNumber>3</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM4508-GLS-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>1</ns2:orderQty><ns2:description>Perla Venato Gloss</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Gloss</ns2:finish><ns2:color>Perla Venato</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line><ns2:line><ns2:lineNumber>4</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM0476-GLS-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>1</ns2:orderQty><ns2:description>Calcite</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Gloss</ns2:finish><ns2:color>Calcite</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line><ns2:line><ns2:lineNumber>5</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM0478-MAT-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>1</ns2:orderQty><ns2:description>Carrara</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Matte</ns2:finish><ns2:color>Carrara</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line><ns2:line><ns2:lineNumber>6</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM4508-GLS-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>1</ns2:orderQty><ns2:description>Perla Venato Gloss</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Gloss</ns2:finish><ns2:color>Perla Venato</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line></ns2:order><ns2:deliveryAddress><ns2:salutation/><ns2:businessName/><ns2:firstName>Janet</ns2:firstName><ns2:lastName>Graham</ns2:lastName><ns2:line1>2A River St</ns2:line1><ns2:line2/><ns2:line3/><ns2:line4/><ns2:city>Birchgrove</ns2:city><ns2:suburb>Birchgrove</ns2:suburb><ns2:state>NSW</ns2:state><ns2:postalCode>2041</ns2:postalCode><ns2:country/><ns2:instructions/><ns2:phone></ns2:phone></ns2:deliveryAddress><ns2:lead><ns2:firstName/><ns2:lastName/><ns2:company/><ns2:aboutMe>AnD-Interior Designer</ns2:aboutMe><ns2:emailOptIn/><ns2:contactByFabricator/><ns2:description/><ns2:Project><ns2:name/><ns2:location/></ns2:Project><ns2:Contact><ns2:title/><ns2:email/><ns2:phone/><ns2:street/><ns2:city/><ns2:state/><ns2:postalCode/></ns2:Contact></ns2:lead><ns2:TraceInfo><com:processId xmlns:com="http://fbu.com/common">74a780cb-3cb2-4c0c-b67f-54de8872ded6</com:processId><com:processName xmlns:com="http://fbu.com/common">LaminexCreateSampleOrder</com:processName><com:uniqueIdentifier xmlns:com="http://fbu.com/common"/></ns2:TraceInfo></ns2:createOrderRequest></soapenv:Body>', '84a780cb-3cb2-4c0c-b67f-54de8872ded6,4287411,<soapenv:Body xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:lam="http://fbu.com/BuildingProducts/LaminexEcomSampleProductOrchestrator" xmlns:com="http://fbu.com/common"><ns2:createOrderRequest xmlns:ns2="http://fbu.com/BuildingProducts/LaminexEcomSampleProductOrchestrator"><ns2:erpId>AU-1067063</ns2:erpId><ns2:leadId/><ns2:salesforceCompanyId>0010X00004Ry1jWQAR</ns2:salesforceCompanyId><ns2:userId>0030X00002T9uJiQAJ</ns2:userId><ns2:userName>janetgrahaminteriors@gmail.com</ns2:userName><ns2:orderNo/><ns2:phoneNumber/><ns2:orderTotal>0.0</ns2:orderTotal><ns2:optIn/><ns2:processId>ef6ab9fb-bb75-480c-8a94-3169f917cc80</ns2:processId><ns2:relatedProjectInformation>Mosman home+Residential Renovation</ns2:relatedProjectInformation><ns2:creationTime>2021-03-30T12:57:57.211GMT+11</ns2:creationTime><ns2:order><ns2:line><ns2:lineNumber>1</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM4507-GLS-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>2</ns2:orderQty><ns2:description>Milano Venato Gloss</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Gloss</ns2:finish><ns2:color>Milano Venato</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line><ns2:line><ns2:lineNumber>2</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM0489-GLS-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>1</ns2:orderQty><ns2:description>Pure Cloud</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Gloss</ns2:finish><ns2:color>Pure Cloud</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line><ns2:line><ns2:lineNumber>3</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM4508-GLS-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>1</ns2:orderQty><ns2:description>Perla Venato Gloss</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Gloss</ns2:finish><ns2:color>Perla Venato</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line><ns2:line><ns2:lineNumber>4</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM0476-GLS-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>1</ns2:orderQty><ns2:description>Calcite</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Gloss</ns2:finish><ns2:color>Calcite</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line><ns2:line><ns2:lineNumber>5</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM0478-MAT-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>1</ns2:orderQty><ns2:description>Carrara</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Matte</ns2:finish><ns2:color>Carrara</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line><ns2:line><ns2:lineNumber>6</ns2:lineNumber><ns2:productCode>993180</ns2:productCode><ns2:sampleProductCode>LAM4508-GLS-LS-12x6</ns2:sampleProductCode><ns2:price>0.0</ns2:price><ns2:orderQty>1</ns2:orderQty><ns2:description>Perla Venato Gloss</ns2:description><ns2:deliveryType>STANDARD</ns2:deliveryType><ns2:marketingRange>Essastone</ns2:marketingRange><ns2:size>120x60x3mm</ns2:size><ns2:finish>Gloss</ns2:finish><ns2:color>Perla Venato</ns2:color><ns2:brand>Essastone</ns2:brand><ns2:categoryCode>993180</ns2:categoryCode></ns2:line></ns2:order><ns2:deliveryAddress><ns2:salutation/><ns2:businessName/><ns2:firstName>Janet</ns2:firstName><ns2:lastName>Graham</ns2:lastName><ns2:line1>2A River St</ns2:line1><ns2:line2/><ns2:line3/><ns2:line4/><ns2:city>Birchgrove</ns2:city><ns2:suburb>Birchgrove</ns2:suburb><ns2:state>NSW</ns2:state><ns2:postalCode>2041</ns2:postalCode><ns2:country/><ns2:instructions/><ns2:phone></ns2:phone></ns2:deliveryAddress><ns2:lead><ns2:firstName/><ns2:lastName/><ns2:company/><ns2:aboutMe>AnD-Interior Designer</ns2:aboutMe><ns2:emailOptIn/><ns2:contactByFabricator/><ns2:description/><ns2:Project><ns2:name/><ns2:location/></ns2:Project><ns2:Contact><ns2:title/><ns2:email/><ns2:phone/><ns2:street/><ns2:city/><ns2:state/><ns2:postalCode/></ns2:Contact></ns2:lead><ns2:TraceInfo><com:processId xmlns:com="http://fbu.com/common">74a780cb-3cb2-4c0c-b67f-54de8872ded6</com:processId><com:processName xmlns:com="http://fbu.com/common">LaminexCreateSampleOrder</com:processName><com:uniqueIdentifier xmlns:com="http://fbu.com/common"/></ns2:TraceInfo></ns2:createOrderRequest></soapenv:Body>']

    # # # post_to_ConverterProxy(final_payload_list, UUID_list)

    # file_list = list_files_in_input_dir()
    # for filename in file_list:
    #     transform_exports_csv(filename)

    # transform_exports_csv('cats.csv')

main()
