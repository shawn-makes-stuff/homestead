# Homestead.dll (RED4ext plugin). Needs the RED4ext SDK (https://github.com/WopsS/RED4ext.SDK):
#   cmake -S plugin -B plugin/build -DRED4EXT_SDK=D:/tools/RED4ext.SDK && cmake --build plugin/build --config Release
cmake_minimum_required(VERSION 3.21)
project(Homestead LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(RED4EXT_SDK "D:/tools/RED4ext.SDK" CACHE PATH "the RED4ext SDK")
set(RED4EXT_HEADER_ONLY ON CACHE BOOL "" FORCE)
add_subdirectory(${RED4EXT_SDK} red4ext_sdk EXCLUDE_FROM_ALL)
add_library(Homestead SHARED Main.cpp)
target_link_libraries(Homestead PRIVATE RED4ext::SDK winhttp)
target_compile_definitions(Homestead PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX)
set_property(TARGET Homestead PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded")   # (no VC++ runtime needed on the player's PC)
