import adsk.core
import os
from ...lib import fusion360utils as futil
from ... import config
from .create_honeycomb import *
app = adsk.core.Application.get()
ui = app.userInterface
honeyComb = HoneyComb(app, ui)

def round_to_nearest_half_mm(value_cm):
    # Convert from cm to mm, round to the nearest 0.5 mm, and then convert back to cm
    value_mm = value_cm * 10  # Convert cm to mm
    rounded_value_mm = round(value_mm * 2) / 2  # Round to the nearest 0.5 mm
    rounded_value_cm = rounded_value_mm / 10  # Convert back to cm
    return rounded_value_cm


# TODO *** Specify the command identity information. ***
CMD_ID = f'citizenbean_create_honeycomb_cmdDialog'
CMD_NAME = 'Create Honeycomb Pattern'
CMD_Description = 'Create a honeycomb pattern in a sketch.'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = 'FusionSolidEnvironment' # FusionDrawingsBlockEditorEnv # FusionDrawingsSketchEnv # SchEditorEnvironement 
PANEL_ID = 'SketchCreatePanel'
COMMAND_BESIDE_ID = 'ScriptsManagerCommand'

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []




# Executed when add-in is run.
def start():
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get the panel the button will be created in.
    panel = workspace.toolbarPanels.itemById(PANEL_ID)

    # Create the button command control in the UI after the specified existing command.
    control = panel.controls.addCommand(cmd_def)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # TODO Define the dialog for your command by adding different inputs to the command.

    selectInput = inputs.addSelectionInput("CreateHexagonProfile", "Select Profile", "Select the profiles to create hexagons in")
    selectInput.addSelectionFilter("Profiles")
    selectInput.setSelectionLimits(1)

    hex_diameter_input = inputs.addFloatSpinnerCommandInput('hexDiameterInput', 'Hex Diameter', 'mm', 0.5, float('inf'), 0.5, 20) 
    hex_diameter_input.isVisible = False  # Initially hide

    padding_input = inputs.addFloatSpinnerCommandInput('paddingInput', 'Padding', 'mm', 0.1, float('inf'), 0.1, 2.0) 
    padding_input.isVisible = False  # Initially hide

    # TODO Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')
    honeyComb.reset()
    inputs = args.command.commandInputs

    selectInput = inputs.itemById('CreateHexagonProfile')
    hex_diameter_input = inputs.itemById('hexDiameterInput')
    padding_input = inputs.itemById('paddingInput')

    profile = selectInput.selection(0).entity
    hex_diameter = hex_diameter_input.value
    padding = padding_input.value

    honeyComb.create(profile, hex_diameter, padding)
    honeyComb.commit()


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')

    honeyComb.reset()
    inputs = args.command.commandInputs

    selectInput = inputs.itemById('CreateHexagonProfile')
    hex_diameter_input = inputs.itemById('hexDiameterInput')
    padding_input = inputs.itemById('paddingInput')

    profile = selectInput.selection(0).entity
    hex_diameter = hex_diameter_input.value
    padding = padding_input.value

    honeyComb.create(profile, hex_diameter, padding)


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs
    
    if changed_input.id == 'CreateHexagonProfile':  # Check if the profile selection changed
        selectInput = inputs.itemById('CreateHexagonProfile')
        hex_diameter_input = inputs.itemById('hexDiameterInput')
        padding_input = inputs.itemById('paddingInput')

        hex_diameter_input.isVisible = selectInput.selectionCount > 0  # Show if a profile is selected
        padding_input.isVisible = selectInput.selectionCount > 0  

        if selectInput.selectionCount > 0:
            profile = selectInput.selection(0).entity

            profile_area = profile.areaProperties().area
            desired_infill_percentage = 0.1  # 20% infill
            hexagon_area = profile_area * desired_infill_percentage

            side_length = math.sqrt((2 * hexagon_area) / (3 * math.sqrt(3)))

            minimum_wall_thickness = side_length * 0.1

            suggestedHexDiameter = round_to_nearest_half_mm(2 * side_length)
            suggestedPadding = round_to_nearest_half_mm(suggestedHexDiameter * 0.1)

            hex_diameter_input.value = suggestedHexDiameter
            padding_input.value = suggestedPadding
        
            args.command.executePreview()

    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    #futil.log(f'{CMD_NAME} Validate Input Event')
    pass
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []
