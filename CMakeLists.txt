cmake_minimum_required(VERSION 2.8.9)

project(BaseNav)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "http://www.example.com/Slicer/Extensions/BaseNav")
set(EXTENSION_CATEGORY "IGT")
set(EXTENSION_CONTRIBUTORS "Andras Lasso, Tamas Ungi (Perk Lab)")
set(EXTENSION_DESCRIPTION "This extension is for navigation of breast tumor excision surgery.")
set(EXTENSION_ICONURL "http://www.example.com/Slicer/Extensions/BaseNav.png")
set(EXTENSION_SCREENSHOTURLS "http://www.example.com/Slicer/Extensions/BaseNav/Screenshots/1.png")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(BaseNav)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_CPACK})
