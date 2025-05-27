cmake_minimum_required(VERSION 3.15)

if(NOT DEFINED SKBUILD_PROJECT_NAME)
  get_filename_component(SKBUILD_PROJECT_NAME ${CMAKE_SOURCE_DIR} NAME)
endif()

project(${SKBUILD_PROJECT_NAME} LANGUAGES C)
set(CMAKE_C_STANDARD 23)
set(CMAKE_COMPILE_WARNING_AS_ERROR ON)
add_compile_options(-Wall -Wextra -pedantic)

include(FetchContent)
FetchContent_Declare(
  stb
  GIT_REPOSITORY https://github.com/nothings/stb.git
  GIT_TAG f58f558c120e9b32c217290b80bad1a0729fbb2c
  GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(stb)
add_library(stb INTERFACE)
target_include_directories(stb SYSTEM INTERFACE ${stb_SOURCE_DIR})

find_package(Python COMPONENTS Development.Module REQUIRED)
find_package(LibXml2 REQUIRED)

file(GLOB C_FILES "*.c")
foreach(C_FILE ${C_FILES})
  get_filename_component(MODULE_NAME ${C_FILE} NAME_WE)
  python_add_library(${MODULE_NAME} MODULE ${C_FILE} WITH_SOABI)
  install(TARGETS ${MODULE_NAME} DESTINATION ${SKBUILD_PROJECT_NAME})

  set(PYI_FILE ${MODULE_NAME}.pyi)
  if(EXISTS ${PYI_FILE})
    install(FILES ${PYI_FILE} DESTINATION ${SKBUILD_PROJECT_NAME})
  endif()

  target_link_libraries(${MODULE_NAME} PRIVATE stb)
endforeach()

target_link_libraries(xml_parse PRIVATE LibXml2::LibXml2)
target_link_libraries(xml_unparse PRIVATE LibXml2::LibXml2)
