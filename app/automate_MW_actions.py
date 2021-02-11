import os

# ----------------------------------------------------------------------
# Define exports directory here (remember a / on the end of the path buddy):
# ----------------------------------------------------------------------
exports_dir = 'C:/dev/Cole/Project Notes/Laminex Ecommerce - MW Actions/@ Python Script/exports_dir/'

def list_files_in_exports_dir():
    # get a list of all filenames currently inside the unprocessed export.csv directory.

    print("Fetching list of CSV files to be processed...")

    print("exports_dir: {}".format(exports_dir)) # delete
    pass


def transform_exports_csv(filename):
    # for each file found inside list_files_in_exports_dir, now read this file, and return its contents.

    print("Reading contents of file --> {}".format(filename))

    if os.path.isfile(exports_dir + filename):
        with open(exports_dir + filename) as file:
            print(file.read())
            # data = json.load(file)
    else:
        print("{} not found!".format(filename))
        return None


def main():
    print("Starting automate_MW_actions.py...")
    # file_list = list_files_in_exports_dir()

    # for filename in file_list:
    #     transform_exports_csv(filename)

    transform_exports_csv('cats.txt')

main()
