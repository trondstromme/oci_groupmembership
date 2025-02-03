import sys
import os
import oci

# NOTE, this is python, but maybe not python as Guido van Rossum would write it
# there are probably much better ways to write it, I'm learning..

class Importer:
        def __init__(self):
            self.to = None
            self.id = None

        def setResource(self, s):
            self.to = s

        def setId(self, id):
            self.id = id

        def toString(self):
            sb = []
            sb.append("import{\n")
            sb.append("    to = ")
            sb.append(self.to)
            sb.append("\n")
            sb.append("    id = \"")
            sb.append(self.id)
            sb.append("\"\n}\n")
            return ''.join(sb)

class FileReader:
    def main(self):

        path = sys.argv[1]
        config = oci.config.from_file()
        id_client = oci.identity.IdentityClient(config)

        try:
            with open(path, 'r') as file:
                lines = file.readlines()
            no_lines = len(lines)
            imp = None
            i = 0
            while i < no_lines:
                line = lines[i].strip()
                if "ocid" not in line:
                    imp = Importer()
                    imp.setResource(line)
                    i += 1
                else:
                    bob = id_client.list_user_group_memberships(compartment_id=config["tenancy"], user_id=line)
                    imp.setId(bob.data[0].id)
                    i += 1
                if imp.id is not None:
                    print(imp.toString())
        except Exception as e:
            print(e)

if len(sys.argv) != 2:
    print("need a path to the resource/ocid list!")
    exit(os.EX_USAGE)

fileReader = FileReader()
fileReader.main()

