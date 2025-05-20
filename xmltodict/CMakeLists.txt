cmake_minimum_required(VERSION 3.15)

if(NOT DEFINED SKBUILD_PROJECT_NAME)
  get_filename_component(SKBUILD_PROJECT_NAME ${CMAKE_SOURCE_DIR} NAME)
endif()

project(${SKBUILD_PROJECT_NAME} LANGUAGES C)

find_package(Python COMPONENTS Development.Module REQUIRED)
find_package(LibXml2 REQUIRED)

python_add_library(parse MODULE parse.c WITH_SOABI)
target_compile_features(parse PUBLIC c_std_23)
target_link_libraries(parse PRIVATE LibXml2::LibXml2)
install(TARGETS parse DESTINATION ${SKBUILD_PROJECT_NAME})
