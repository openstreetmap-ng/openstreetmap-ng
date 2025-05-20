cmake_minimum_required(VERSION 3.15)

if(NOT DEFINED SKBUILD_PROJECT_NAME)
  get_filename_component(SKBUILD_PROJECT_NAME ${CMAKE_SOURCE_DIR} NAME)
endif()

project(${SKBUILD_PROJECT_NAME} LANGUAGES C)

set(CMAKE_C_STANDARD 23)

find_package(Python COMPONENTS Development.Module REQUIRED)
find_package(LibXml2 REQUIRED)

python_add_library(xml_parse MODULE xml_parse.c WITH_SOABI)
target_link_libraries(xml_parse PRIVATE LibXml2::LibXml2)
install(TARGETS xml_parse DESTINATION ${SKBUILD_PROJECT_NAME})
install(FILES xml_parse.pyi DESTINATION ${SKBUILD_PROJECT_NAME})
