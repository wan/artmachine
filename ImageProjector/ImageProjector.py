# ImageProjector.py: A script for generating 3d-point casting images
import sys, os
import pathlib

# Add local requirements to working path. See README.md for more details
script_abspath = pathlib.Path(__file__).parent.absolute()
packagepath = os.path.join(script_abspath, "packages")
if packagepath not in sys.path:
    sys.path.append(packagepath)

import adsk.core, adsk.fusion, traceback
import math
import random
import imageio
from PIL import ImageStat, Image, ImageOps
import mercantile

commandId = 'ImageProjector'
workspaceToUse = 'FusionSolidEnvironment'
panelToUse = 'SolidCreatePanel'

handlers = []

def commandDefinitionById(_id):
    app = adsk.core.Application.get()
    ui = app.userInterface
    if not _id:
        ui.messageBox('commandDefinition id is not specified')
        return None
    commandDefinitions_ = ui.commandDefinitions
    commandDefinition_ = commandDefinitions_.itemById(_id)
    return commandDefinition_

def getToolbarControls():
    toolbarControls_ = None
    app = adsk.core.Application.get()
    ui = app.userInterface
    workspaces_ = ui.workspaces
    modelingWorkspace_ = workspaces_.itemById(workspaceToUse)
    if modelingWorkspace_:
        toolbarPanels_ = modelingWorkspace_.toolbarPanels
        toolbarPanel_ = toolbarPanels_.itemById(panelToUse)
        if (toolbarPanel_):
            toolbarControls_ = toolbarPanel_.controls
    return toolbarControls_

def commandControlById(_id):
    app = adsk.core.Application.get()
    ui = app.userInterface
    if not _id:
        ui.messageBox('commandControl id is not specified')
        return None
    
    toolbarControls_ = getToolbarControls()
    if not toolbarControls_:
        ui.messageBox('Unable to find Toolbar Controls for "' + workspaceToUse + '.' + panelToUse + '"')
        return None

    toolbarControl_ = toolbarControls_.itemById(_id)
    return toolbarControl_

def destroyObject(uiObj, tobeDeleteObj):
    if uiObj and tobeDeleteObj:
        if tobeDeleteObj.isValid:
            tobeDeleteObj.deleteMe()
        else:
            uiObj.messageBox('tobeDeleteObj is not a valid object')

def generateImageProjection(params):
    app = adsk.core.Application.get()
    ui  = app.userInterface
    root = app.activeProduct.rootComponent

    # Parse parameters
    body = params['selectedBodies'][0]
    samples = params['samples']
    invertColor = params['invertColor']
    mirror = params['mirror']
    apertureRadius = params['apertureRadius']
    imageName = params['imageName']
    # zoom defines the tiling zoom level used with the mercantile library. Check the mercantile docs for more
    # It used to be a passable param, but 7 has been reasonable in practice - there's a tradeoff between the number of tiles
    zoom = 7

    # Load and process the image. Draw holes in white areas of the images (unless invertColor is set)
    if not os.path.exists(imageName):
        ui.messageBox("Image %s could not be found!" % imageName)
        return

    # Simple origin. Ideally we'd pick the center of the selected body, or define one manually.
    origin = adsk.core.Point3D.create(0, 0, 0)
    try:
        img = imageio.imread(imageName, pilmode='L')
    except:
        ui.messageBox("Could not process image!")
        return

    offset = 2.0/samples
    increment = math.pi * (3.0 - math.sqrt(5.0))
    rnd = 1.0

    if invertColor:
        img = 1 - img

    # The main loop. We'll be iterating around the sphere using a Fibonacci lattice with N=samples vertices.
    # At each vertex use mercator to define a tile containing the vertex, which we use to sample the image.
    # For each tile, add a cutting body (cone) with base radius proportional to the mean image brightness of the tile.
    # After iterating, use the union of all the cutting bodies as a tool body and combine-cut the target body.
    tempBRep = adsk.fusion.TemporaryBRepManager.get()
    maxLat = 85.0511
    height, width = img.shape[:2]
    coords = []
    maxBr = -1
    nBodies = 1

    # r defines the length of the cutting body. May need to be rescaled if your projects are larger than ~24 units across.
    # It could be a parameter but I've left it constant in favor of using apertureRadius.
    r = 48
    oRadius = 0.001# radius of the pointy (non-cutting) end of projection cones

    toolBody = tempBRep.createSphere(origin, 1)
    batch = 0

    for i in range(samples):
        # Generate lattice coordinates and convert to Cartesian
        index = i + 0.5
        phi = math.acos(1 - 2*(index/samples))
        theta = math.pi * (1 + 5**0.5) * index

        x = math.cos(theta) * math.sin(phi)
        y = math.sin(theta) * math.sin(phi)
        z = math.cos(phi)

        x *= r
        y *= r
        z *= r

        # Convert to lat/lng ranges for mercator projection
        centerLat = math.degrees(phi) - 90.0
        if mirror:
            centerLng = 180 - (math.degrees(theta) % 360.0)
        else:
            centerLng = math.degrees(theta) % 360 - 180

        tile = mercantile.tile(centerLng, centerLat, zoom)
        bounds = mercantile.bounds(tile)

        # Convert to noramlized coords for image sampling
        west = (180 + bounds.west)
        east = (180 + bounds.east)
        north = (maxLat + bounds.north)
        south = (maxLat + bounds.south)
        west = int((west/360) * width)
        east = int((east/360) * width)
        north = int((north/(2*maxLat)) * height)
        south = int((south/(2*maxLat)) * height)
        
        # Sample and find brightness
        cropped = img[south:north, west:east]
        cImg = Image.fromarray(cropped)
        stat = ImageStat.Stat(cImg)
        try:
            brightness = stat.rms[0]/255.0
            maxBr = max(maxBr, brightness)
        except:
            continue

        # Set cutting radius and add a tool body
        pRadius = apertureRadius*(brightness*brightness)
        if pRadius < oRadius:
            continue
        p2 = adsk.core.Point3D.create(x, y, z)
        cone = tempBRep.createCylinderOrCone(origin, oRadius, p2, pRadius)
        try:
            tempBRep.booleanOperation(toolBody, cone, adsk.fusion.BooleanTypes.UnionBooleanType)
            batch += 1
        except:
            continue

        coords.append(p2)

    # Start editing and run the cut operation
    baseFeatures = root.features.baseFeatures.add()
    baseFeatures.startEdit()
    root.bRepBodies.add(toolBody, baseFeatures)
    baseFeatures.finishEdit()

    toolBodies = adsk.core.ObjectCollection.create()
    toolBodies.add(baseFeatures.bodies.item(0))

    combineFeatures = root.features.combineFeatures
    combineInput = combineFeatures.createInput(body, toolBodies)
    combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combineInput.isKeepToolBodies = False
    combineFeatures.add(combineInput)

    app.activeViewport.fit()
    ui.messageBox("Searched %s sample points, cut with %s tool bodies with apeture scale %s" % (samples, len(coords), apertureRadius))

    return

class ImageProjectorCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface
        print("Command was created")

        try:
            eventArgs = adsk.core.CommandCreatedEventArgs.cast(args)
            command = eventArgs.command

            onExecute = ImageProjectorExecuteHandler()
            command.execute.add(onExecute)

            onDestroy = ImageProjectorDestroyHandler()
            command.destroy.add(onDestroy)

            onInputChanged = ImageProjectorInputChangedHandler()
            command.inputChanged.add(onInputChanged)

            handlers.append(onExecute)
            handlers.append(onDestroy)
            handlers.append(onInputChanged)

            inputs = command.commandInputs

            projectionBodyInput = inputs.addSelectionInput('projectionBody', 'Projection Body', 'Select a body to project image through')
            projectionBodyInput.addSelectionFilter('Bodies')
            projectionBodyInput.setSelectionLimits(0)

            imageNameInput = inputs.addStringValueInput('imageName', 'Image Filename', 'Path to image file')

            samplesInput = inputs.addIntegerSpinnerCommandInput('samples', 'Number of sample points', 256, 24000, 32, 4096)

            apertureRadiusInput = inputs.addFloatSpinnerCommandInput('apertureRadius', 'Aperture radius scale', '', 0.01, 10.0, 0.01, 1.0)

            invertColorInput = inputs.addBoolValueInput('invertColor', 'Invert colors (default: white -> holes, black -> solid)', True)

            mirrorInput = inputs.addBoolValueInput('mirror', 'Mirror x-axis', True)

        except:
            ui.messageBox('Failed to create image projection command\n{}'.format(traceback.format_exc()))

class ImageProjectorInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            cmd = args.firingEvent.sender
            inputs = cmd.commandInputs
        except:
            ui.messageBox('Failed to process input changes\n{}'.format(traceback.format_exc()))

class ImageProjectorDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        adsk.terminate()

class ImageProjectorExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
        
    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui  = app.userInterface
            design = app.activeProduct
            if not design:
                ui.messageBox('No active design', appTitle)
                return

            command = args.firingEvent.sender
            inputs = command.commandInputs
            params = {
                'selectedBodies': [],
                'projectionDistance': 12, # presumably inches, hardcoded for now
                'imageName': None,
                'invertColor': False,
                'mirror': False,
                'apertureRadius': 1.0,
                'samples': 4096
            }

            for input_ in inputs:
                if input_.id == 'imageName':
                    params['imageName'] = input_.value
                elif input_.id == 'invertColor':
                    params['invertColor'] = input_.value
                elif input_.id == 'mirror':
                    params['mirror'] = input_.value
                elif input_.id == 'apertureRadius':
                    params['apertureRadius'] = input_.value
                elif input_.id == 'samples':
                    params['samples'] = input_.value
                elif input_.id == 'projectionBody':
                    for idx in range(input_.selectionCount):
                        params['selectedBodies'].append(input_.selection(idx).entity)
                    if not params['selectedBodies']:
                        ui.messageBox('Failed to get selected body.')
                        return

            generateImageProjection(params)

        except:
            ui.messageBox('Failed to execute image projection command\n{}'.format(traceback.format_exc()))

def run(context):
    title = 'Image Projector'
    app = adsk.core.Application.get()
    ui = app.userInterface

    commandName = 'Image Projector'
    commandDescription = "Creates an image projection body"
    commandResources = './resources'
   
    try:
        cmdDef = ui.commandDefinitions.itemById(commandId)
        if not cmdDef:
            cmdDef = ui.commandDefinitions.addButtonDefinition(commandId, commandName, commandDescription)
        
        onCommandCreated = ImageProjectorCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        handlers.append(onCommandCreated)

        inputs = adsk.core.NamedValues.create()
        cmdDef.execute(inputs)

        adsk.autoTerminate(False)
    except:
        if ui:
            ui.messageBox("Script failed\n{}".format(traceback.format_exc()))

def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        objArray = []

        commandControl_ = commandControlById(commandId)
        if commandControl_:
            objArray.append(commandControl_)

        commandDefinition_ = commandDefinitionById(commandId)
        if commandDefinition_:
            objArray.append(commandDefinition_)

        for obj in objArray:
            destroyObject(ui, obj)

    except:
        if ui:
            ui.messageBox('AddIn Stop Failed\n{}'.format(traceback.format_exc()))
