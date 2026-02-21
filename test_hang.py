import sys
import faulthandler
faulthandler.enable()

from pairwise_cli.cli import cmd_doctor

class DummyArgs:
    command = "doctor"

print("Calling cmd_doctor")
cmd_doctor(DummyArgs())
print("Done cmd_doctor")
