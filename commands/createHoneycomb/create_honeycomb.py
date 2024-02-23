import adsk.core, adsk.fusion, adsk.cam, traceback, math

class HoneyComb:
    def __init__(self, app: adsk.core.Application, ui: adsk.core.UserInterface):
        self.app = app
        self.ui = ui
        self.design = app.activeProduct
        self.root = self.design.rootComponent
        self.created_lines = adsk.core.ObjectCollection.create()
        self.lines_to_delete = adsk.core.ObjectCollection.create()

    def reset(self):
        self.clearList(self.created_lines, True)
        self.clearList(self.lines_to_delete, True)
    
    def commit(self):
        self.clearList(self.created_lines, False)
        self.clearList(self.lines_to_delete, True)

    def clearList(self, list: adsk.core.ObjectCollection, deleteEntities: bool = False):
        for item in list.asArray():
            if not item.isValid:
                list.removeByItem(item)
        
        if deleteEntities and list.count > 0:
            self.design.deleteEntities(list)

        list.clear()

    def create(self, profile: adsk.fusion.Profile, hexDiameter: float, padding: float):
        if hexDiameter <= 0 or padding <= 0:
            self.ui.messageBox('Invalid input values. Please ensure all inputs are positive numbers.')
            return
        
        self.reset()
        
        sketch = profile.parentSketch
        sketch.isComputeDeferred = True  # Improve performance during sketch creation

        hexRadius, colWidth, rowHeight = self.generateHexagonDimensions(hexDiameter, padding)
        
        boundingBox = profile.boundingBox
        minX = boundingBox.minPoint.x
        minY = boundingBox.minPoint.y
        maxX = boundingBox.maxPoint.x
        maxY = boundingBox.maxPoint.y

        center_points = []

        proximity_threshold = hexDiameter * 0.25

        influenceZone = adsk.core.BoundingBox3D.create(
            adsk.core.Point3D.create(minX - hexRadius * 2, minY - hexRadius * 2, boundingBox.minPoint.z),
            adsk.core.Point3D.create(maxX + hexRadius * 2, maxY + hexRadius * 2, boundingBox.maxPoint.z)
        )

        numCols = int((influenceZone.maxPoint.x - influenceZone.minPoint.x) / colWidth) + 1
        numRows = int((influenceZone.maxPoint.y - influenceZone.minPoint.y) / rowHeight) + 1
    
        #line = sketch.sketchCurves.sketchLines.addByTwoPoints(adsk.core.Point3D.create(minX, minY, boundingBox.minPoint.z), adsk.core.Point3D.create(maxX, maxY, boundingBox.minPoint.z))
        #self.created_lines.add(line)

        for row in range(numRows):
            for col in range(numCols):
                xOffset = (col * colWidth) + (row % 2) * (colWidth / 2)
                yOffset = row * rowHeight
                centerPoint = adsk.core.Point3D.create(minX + xOffset, minY + yOffset, boundingBox.minPoint.z)

                # Check if hexagon center is inside profile before creating
                if influenceZone.contains(centerPoint):
                    outerHexagon = self.createHexagon(sketch, centerPoint, hexRadius)
                    self.clipHexagonToProfile(sketch, outerHexagon, profile)
        
        if self.lines_to_delete.count > 0:
            self.design.deleteEntities(self.lines_to_delete)
            self.lines_to_delete.clear()

        sketch.isComputeDeferred = False
    
    def generateHexagonDimensions(self, hexDiameter: float, padding: float):
        hexRadius = hexDiameter / 2.0
        hexWidth = hexRadius * math.cos(math.pi / 6.0)
        hexHeight = hexRadius * 1.5
        colWidth = 2.0 * hexWidth + padding
        rowHeight = hexHeight + padding

        return hexRadius, colWidth, rowHeight

    def createHexagon(self, sketch: adsk.fusion.Sketch, centerPoint: adsk.core.Point3D, radius: float):
        sketchLines = sketch.sketchCurves.sketchLines

        outerPoints = []
        outerLines = [] 
        for i in range(6):
            angle_deg = 60 * i - 30
            angle_rad = math.radians(angle_deg)
            x = centerPoint.x + radius * math.cos(angle_rad)
            y = centerPoint.y + radius * math.sin(angle_rad)
            p = adsk.core.Point3D.create(x, y, centerPoint.z)
            outerPoints.append(p)
            
        for i in range(6):
            line = sketchLines.addByTwoPoints(outerPoints[i], outerPoints[(i + 1) % 6])
            self.created_lines.add(line)
            outerLines.append(line)
        
        return outerLines

    def clipHexagonToProfile(self, sketch: adsk.fusion.Sketch, hexagonLines: [adsk.fusion.SketchLine], profile: adsk.fusion.Profile):
        for line in hexagonLines:
            self.clipLineToProfile(sketch, line, profile)

    def clipLineToProfile(self, sketch: adsk.fusion.Sketch, line: adsk.fusion.SketchLine, profile: adsk.fusion.Profile):
        startPoint = line.startSketchPoint.geometry
        endPoint = line.endSketchPoint.geometry

        startPointInsideProfile = self.isPointInsideProfile(startPoint, profile)
        endPointInsideProfile = self.isPointInsideProfile(endPoint, profile)

        if startPointInsideProfile and endPointInsideProfile:
            return

        if not startPointInsideProfile and not endPointInsideProfile:
            self.lines_to_delete.add(line)
            return

        intersections = []

        sketchCurves = adsk.core.ObjectCollection.create()
        for loop in profile.profileLoops:
            for curve in loop.profileCurves:
                sketchCurves.add(curve.sketchEntity)

        (success, intersectingCurves, intersectingPoints) = line.intersections(sketchCurves)
        if success:
            intersections.extend(intersectingPoints.asArray())

        if not intersectingPoints and not intersectingCurves:
            self.lines_to_delete.add(line)
            return    
        # Sort intersections by distance from start point
        intersections.sort(key=lambda pt: startPoint.distanceTo(pt))

        new_start_point = startPoint
        if not startPointInsideProfile:
            intersections.reverse()
            new_start_point = endPoint
        
        for i in range(len(intersections)):
            if i % 2 == 0:
                l = sketch.sketchCurves.sketchLines.addByTwoPoints(new_start_point, intersections[i])
                self.created_lines.add(l)
            if i % 2 == 1:
                new_start_point = intersections[i]

        self.lines_to_delete.add(line)

    def isPointInsideProfile(self, point, profile):
        if not profile.boundingBox.contains(point):
            return False

        sketch = profile.parentSketch

        temp_line = sketch.sketchCurves.sketchLines.addByTwoPoints(point, adsk.core.Point3D.create(profile.boundingBox.maxPoint.x + 1, profile.boundingBox.maxPoint.y + 1, profile.boundingBox.maxPoint.z))
        self.lines_to_delete.add(temp_line)

        sketchCurves = adsk.core.ObjectCollection.create()
        for loop in profile.profileLoops:
            for curve in loop.profileCurves:
                sketchCurves.add(curve.sketchEntity)

        (success, intersectingCurves, intersectingPoints) = temp_line.intersections(sketchCurves)
        
        return success and intersectingPoints.count % 2 == 1
        
        # Count the number of times this line intersects with the profile.
        numIntersects = 0
        for curve in sketchCurves.asArray():
            intersections = line.intersectWithCurve(curve)
            for intersectionPoint in intersections.asArray():
                if point.isEqualToByTolerance(intersectionPoint, 0.001):
                    return True
            numIntersects += intersections.count
        
        # If the number of intersections is odd, the point is inside. If even, it's outside.
        return numIntersects % 2 == 1