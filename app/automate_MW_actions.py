import os
import re
import json
import datetime
import cx_Oracle

# ----------------------------------------------------------------------
# Define directories here! (remember a / on the end of the path buddy):
# ----------------------------------------------------------------------
input_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/exports_dir/'
output_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/output_dir/'
archive_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/archive_dir/'
# ----------------------------------------------------------------------


def fetch_UUIDs_from_csv():
    pass

    # - Read in the csv file from directory, I will save it manually from roger's email
    # - fetch UUID list from csv
    # - fetch orderNo for each UUID from the list too bc i need it for backup SQL statement! probs need to pass them through as lists then
    # - close excel file (important for MOVE.bat later)


def get_audit_db_original_requests(UUIDs):

    ### fetch database credentials:
    print("Fetching Database credentials from file...")

    credentials_path = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/credentials.json'

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

    # Create a table in Oracle database
    try:
        print("Querying middleware database...")
        conn_str = '{0}/{1}@{2}:{3}/{4}'.format(username, password, hostname, port, service_name)
        # print(conn_str)
        cx_Oracle.init_oracle_client("C:/dev/Program Files/instantclient_19_10/")
        con = cx_Oracle.connect(conn_str)
        cursor = con.cursor()

        format_strings = ','.join(["'%s'"] * len(UUIDs)) # creates template of comma separated %s that is n values long depending how many UUIDs we are searching
        sql = '''
        SELECT a.correlation_id,
        (select TO_CHAR(substr(b.payload,instr(b.payload,'erpOrderNumber>')+15 ,7)) from audit_log_details b where b.phase = 'FINAL' and b.STATE = 'FINISHED' and b.correlation_id = a.correlation_id) as ordernumber_Payload,
        (select c.payload from audit_log_details c where c.comments ='Create Sample Order Orchestration start process' and
        c.correlation_id=a.correlation_id and ROWNUM <= 1) as payload
        from audit_log_Details a where a.phase = 'WAIVENET' and a.STATE = 'ERROR'
        and a.correlation_id in (%s) order by a.correlation_id
        '''  % (format_strings) % tuple(UUIDs)
        cursor.execute(sql)

        for row in cursor:
            print("UUID: ", row[0], "\nOrderNo: ", row[1], "\nPayload: ", row[2], sep="")

        print("Database SELECT v1 performed successfully")
        

        ### backup query if nothing was returned for one of the UUIDs:

        # change this to actual list of failed UUIDs:
        failed_UUIDs = ['bd4cc1fc-81f7-4aa8-9172-98e30e56dd89', 'ef5980b7-eebb-4dfc-8d31-20239fd8dbef']

        # could maybe just iterate the corresponding orderNo's at the final for loop printing the values below.

        format_strings = ','.join(["'%s'"] * len(failed_UUIDs)) # creates template of comma separated %s that is n values long depending how many UUIDs we are searching
        sql = '''
        SELECT correlation_id, '%s' as OrderNo, payload FROM audit_log_details
        WHERE STATE = 'START' and PHASE = 'CREATESAMPLORDR-ORCH'
        and correlation_id in (%s) order by correlation_id
        '''  % ("make this orderNo...", format_strings) % tuple(UUIDs)
        cursor.execute(sql)

        for row in cursor:
            print("UUID: ", row[0], "\nOrderNo: ", row[1], "\nPayload: ", row[2], sep="")

        print("Database SELECT v2 performed successfully")


    except cx_Oracle.DatabaseError as e:
        print("\nERROR in Oracle Database Query:\n\n", e, "\n", sep="")

    # by writing finally if any error occurs
    # then also we can close the all database operation
    finally:
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

    get_audit_db_original_requests(['776606eb-67f3-4ac0-ba34-996e55d0e7b8','625af53b-8ca3-4f52-9dd9-d801a780a1f3'])

    # # get list of all files inside the input_dir currently
    # file_list = list_files_in_input_dir()
    #
    # for filename in file_list:
    #     transform_exports_csv(filename)

    # transform_exports_csv('cats.csv')

main()
