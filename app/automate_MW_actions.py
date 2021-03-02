import os
import re
import datetime

# ----------------------------------------------------------------------
# Define directories here! (remember a / on the end of the path buddy):
# ----------------------------------------------------------------------
input_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/exports_dir/'
output_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/output_dir/'
archive_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/archive_dir/'
# ----------------------------------------------------------------------


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

                # replaced_closings = 'hello, there, my, name, is, cole' # delete me
                final_removed_commas = ""
                line_num = 1
                for line in replaced_closings.splitlines():

                    ### Checking for valid phone numbers:

                    line = 'this is a string where the substring "<ns2:phone>0407445979x</ns2:phone>" is repeated several <ns2:phoneNumber>yeet</ns2:phoneNumber> times'
                    # line = 'this is a string where the substring "<ns2:phone/>" is repeated several <ns2:phoneNumber/>yeet</ns2:phoneNumber> times'
                    # print([(a.start(), a.end()) for a in list(re.finditer('<ns2:phone', line))])
                    # print([(line[a.start():a.start()+30]) for a in list(re.finditer('<ns2:phone', line))])

                    for a in list(re.finditer('<ns2:phone', line)):
                        # If we find an empty phone field, do nothing, otherwise fetch the value + its indexes from inbetween the tags:
                        if line[a.start():a.start()+12] == "<ns2:phone/>":
                            print("empty phone found, skipping") # delete

                        elif line[a.start():a.start()+18] == "<ns2:phoneNumber/>":
                            print("empty phoneNumber found, skipping") # delete

                        else:
                            print("line preview: ", line[a.start():a.start()+35])
                            rest_of_line = line[a.start()+1:-1] # the + 1 removes first < from very start
                            value_opening_index = rest_of_line.find(">")
                            value_closing_index = rest_of_line.find("<")

                            if (value_opening_index != -1) and (value_closing_index != -1):
                                phone_value = rest_of_line[value_opening_index+1:value_closing_index]
                            else:
                                error_msg = "Invalid closing and opening >'s found when looking at <ns2:phone!!! very bad!"
                                raise Exception(error_msg)

                            if phone_value.isdigit(): # if it contains all numbers, its fine, let it slide
                                pass
                            else: # else, has some invalid characters, then we do the following:
                                print("Invalid phone number found:\n--->", phone_value, "<---", sep="")
                                requested_phone_value = input("what you want to change this field to fam?: ")
                                # probably have a final confirmation prompt like:
                                print("Are you sure you want to change the <ns2:phone field to:\n--->", requested_phone_value, "<---", sep="")
                                confirmation = input("yes/no: ")

                                # if confirmation in yes_list:
                                #     final_phone_value = requested_phone_value
                                #     # insert this back into final line value
                                # elif confirmation in no_list:
                                #



                            # pass


                    # for each line, loop through it and print all instances of <ns2:phone, etc.
                    # need to somehow determine if the <ns2:phoneNumber> contains a value or not, E.g. if empty who cares, but if has value, then need...
                    # ...to get the start and end indexes, store, them, so that we know which indexes to replace into at end
                    # all possible inputs are:
                    # <ns2:phoneNumber>yeet</ns2:phoneNumber>
                    # <ns2:phoneNumber/>
                    # <ns2:phone>yeet</ns2:phone>
                    # <ns2:phone/>
                    # if it contains all numbers, its fine, let it slide
                    # else, has some invalid characters, then we do the following:
                    # print(<ns2:phone + next 10 chars)
                    # now ask user "are you happy with this?". accept any kind of input back similar to yes, yep, ya, etc.
                    # name = input("are you happy with this?: ")
                    # print("Hello", name + "!")
                    # if answer is no, nope, etc. THEN prompt them again, this time asking what they want to replace it with
                    # name = input("what you want to change this field to fam?: ")
                    # probably have a final confirmation prompt like:
                    # print("Are you sure you want to change this field <ns2:phone to: ", name + "!")
                    # name = input("yes/no: ")
                    # now have to replace the original value in this line with the new content we want added.



                    ### Checking for valid postcodes:

                    # pass


                    ### checking for extra commas which break the request separators. should only have 2 per line:

                    # this won't work once phone + postcode part is done, need to change input var, and be very careful of that final output varialbe final_removed_commas, because we still need to have the changes from the phone/postcode parts above.

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
                #
                # now = datetime.datetime.now()
                # export_file_name = now.strftime("export_%Y%m%d_%H%M%S%f.csv")
                #
                # with open(output_dir + export_file_name, 'w') as file:
                #     file.write(replaced_closings)
                #     file.close()
                #
                # ### move successfully transformed file to archive_dir:
                # os.replace(input_dir + filename, archive_dir + filename)

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

    # file_list = list_files_in_input_dir()
    #
    # for filename in file_list:
    #     transform_exports_csv(filename)

    transform_exports_csv('cats.csv')

main()
