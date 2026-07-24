cmake_minimum_required(VERSION 3.24)
project(offline_yolo LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(YOLO_WITH_QT "Build Qt6 GUI" ON)
option(YOLO_WITH_ONNXRUNTIME "Build with ONNX Runtime" ON)
option(YOLO_WITH_TENSORRT "Build with TensorRT" OFF)
option(YOLO_WITH_CUDA "Build with CUDA support via OpenCV" OFF)
option(YOLO_BUILD_TESTS "Build tests" ON)

# Dependencies
find_package(OpenCV 4 REQUIRED)
find_package(spdlog REQUIRED)
find_package(yaml-cpp REQUIRED)
find_package(nlohmann_json QUIET)
if(NOT nlohmann_json_FOUND)
    # fallback: try to include via FetchContent
    include(FetchContent)
    FetchContent_Declare(
        json
        URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
    )
    FetchContent_MakeAvailable(json)
endif()

# CLI11 - header only
find_package(CLI11 QUIET)
if(NOT CLI11_FOUND)
    include(FetchContent)
    FetchContent_Declare(
        CLI11
        GIT_REPOSITORY https://github.com/CLIUtils/CLI11.git
        GIT_TAG v2.4.2
    )
    FetchContent_MakeAvailable(CLI11)
endif()

# ONNX Runtime - optional
set(ONNXRuntime_FOUND OFF)
if(YOLO_WITH_ONNXRUNTIME)
    find_path(ONNXRUNTIME_INCLUDE_DIR onnxruntime_cxx_api.h
        PATHS /usr/include /usr/local/include /usr/include/onnxruntime
    )
    find_library(ONNXRUNTIME_LIB onnxruntime
        PATHS /usr/lib /usr/local/lib
    )
    if(ONNXRUNTIME_INCLUDE_DIR AND ONNXRUNTIME_LIB)
        set(ONNXRuntime_FOUND ON)
        message(STATUS "Found ONNX Runtime: ${ONNXRUNTIME_INCLUDE_DIR}, ${ONNXRUNTIME_LIB}")
    else()
        message(WARNING "ONNX Runtime not found, will use OpenCV DNN fallback")
    endif()
endif()

# TensorRT optional
if(YOLO_WITH_TENSORRT)
    find_path(TENSORRT_INCLUDE_DIR NvInfer.h
        PATHS /usr/include /usr/local/cuda/include /usr/include/x86_64-linux-gnu
    )
    find_library(TENSORRT_LIB nvinfer
        PATHS /usr/lib /usr/local/cuda/lib64 /usr/lib/x86_64-linux-gnu
    )
    if(TENSORRT_INCLUDE_DIR AND TENSORRT_LIB)
        set(TensorRT_FOUND ON)
        message(STATUS "Found TensorRT")
    else()
        message(WARNING "TensorRT not found")
    endif()
endif()

# Qt6 optional
if(YOLO_WITH_QT)
    find_package(Qt6 COMPONENTS Widgets QUIET)
    if(Qt6_FOUND)
        message(STATUS "Found Qt6")
        set(CMAKE_AUTOMOC ON)
        set(CMAKE_AUTORCC ON)
        set(CMAKE_AUTOUIC ON)
    else()
        message(WARNING "Qt6 not found, building without GUI")
        set(YOLO_WITH_QT OFF)
    endif()
endif()

include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# Core library
file(GLOB_RECURSE CORE_SRCS src/core/*.cpp)
file(GLOB_RECURSE DETECTOR_SRCS src/detector/*.cpp)
file(GLOB_RECURSE SOURCE_SRCS src/source/*.cpp)
file(GLOB_RECURSE PIPELINE_SRCS src/pipeline/*.cpp)
file(GLOB_RECURSE LOGGING_SRCS src/logging/*.cpp)

add_library(yolo_core STATIC
    ${CORE_SRCS}
    ${DETECTOR_SRCS}
    ${SOURCE_SRCS}
    ${PIPELINE_SRCS}
    ${LOGGING_SRCS}
)

target_include_directories(yolo_core PUBLIC include)

target_link_libraries(yolo_core PUBLIC
    opencv_core opencv_imgproc opencv_imgcodecs opencv_videoio opencv_dnn opencv_highgui
    spdlog::spdlog
    yaml-cpp
    nlohmann_json::nlohmann_json
)

if(ONNXRuntime_FOUND)
    target_include_directories(yolo_core PUBLIC ${ONNXRUNTIME_INCLUDE_DIR})
    target_link_libraries(yolo_core PUBLIC ${ONNXRUNTIME_LIB})
    target_compile_definitions(yolo_core PUBLIC YOLO_USE_ONNXRUNTIME=1)
endif()

if(TensorRT_FOUND)
    target_include_directories(yolo_core PUBLIC ${TENSORRT_INCLUDE_DIR})
    target_link_libraries(yolo_core PUBLIC ${TENSORRT_LIB})
    target_compile_definitions(yolo_core PUBLIC YOLO_USE_TENSORRT=1)
endif()

# App executable
add_executable(yolo_app src/app/main.cpp)
target_link_libraries(yolo_app PRIVATE yolo_core CLI11::CLI11)

# GUI executable (monitoring)
if(YOLO_WITH_QT)
    file(GLOB_RECURSE GUI_SRCS src/gui/*.cpp)
    add_executable(yolo_gui src/gui/main_gui.cpp ${GUI_SRCS})
    target_link_libraries(yolo_gui PRIVATE yolo_core Qt6::Widgets CLI11::CLI11)
    # annotator core
    file(GLOB_RECURSE ANNOTATOR_CORE_SRCS src/annotator_core/*.cpp)
    add_library(yolo_annotator_core STATIC ${ANNOTATOR_CORE_SRCS})
    target_link_libraries(yolo_annotator_core PUBLIC yolo_core)
    file(GLOB_RECURSE ANNOTATOR_GUI_SRCS src/annotator_gui/*.cpp)
    add_executable(yolo_annotator src/annotator_gui/main.cpp ${ANNOTATOR_GUI_SRCS})
    target_link_libraries(yolo_annotator PRIVATE yolo_annotator_core Qt6::Widgets CLI11::CLI11)
else()
    # annotator core without QT still builds AI prelabeling logic
    file(GLOB_RECURSE ANNOTATOR_CORE_SRCS src/annotator_core/*.cpp)
    add_library(yolo_annotator_core STATIC ${ANNOTATOR_CORE_SRCS})
    target_link_libraries(yolo_annotator_core PUBLIC yolo_core)
    add_executable(yolo_annotator src/annotator_gui/main.cpp)
    target_link_libraries(yolo_annotator PRIVATE yolo_annotator_core CLI11::CLI11)
endif()

# Tests
if(YOLO_BUILD_TESTS)
    find_package(GTest QUIET)
    if(GTest_FOUND)
        enable_testing()
        file(GLOB TEST_SRCS tests/*.cpp)
        add_executable(yolo_tests ${TEST_SRCS})
        target_link_libraries(yolo_tests PRIVATE yolo_core GTest::GTest GTest::Main)
        add_test(NAME yolo_tests COMMAND yolo_tests)
    else()
        message(STATUS "GTest not found, skipping tests")
    endif()
endif()

# Install
install(TARGETS yolo_app yolo_core
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)
if(YOLO_WITH_QT)
    install(TARGETS yolo_gui yolo_annotator
        RUNTIME DESTINATION bin
    )
else()
    install(TARGETS yolo_annotator
        RUNTIME DESTINATION bin
    )
endif()
