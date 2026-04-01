cmake_minimum_required(VERSION 3.16)
project(koo_viewer LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================
# Third-party dependencies via FetchContent
# ============================================================
include(FetchContent)

# GLFW (window + input + GL context)
FetchContent_Declare(glfw
    GIT_REPOSITORY https://github.com/glfw/glfw.git
    GIT_TAG 3.4
    GIT_SHALLOW ON
)
set(GLFW_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(GLFW_INSTALL OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_WAYLAND OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(glfw)

# Dear ImGui (docking branch)
FetchContent_Declare(imgui
    GIT_REPOSITORY https://github.com/ocornut/imgui.git
    GIT_TAG docking
    GIT_SHALLOW ON
)
FetchContent_MakeAvailable(imgui)

# ImPlot (charts — master branch for ImGui docking compatibility)
FetchContent_Declare(implot
    GIT_REPOSITORY https://github.com/epezent/implot.git
    GIT_TAG master
    GIT_SHALLOW ON
)
FetchContent_MakeAvailable(implot)

# nlohmann/json (JSON parsing)
FetchContent_Declare(nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.3
    GIT_SHALLOW ON
)
set(JSON_BuildTests OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(nlohmann_json)

# ============================================================
# glad (OpenGL 3.3 core loader) — generated single-file
# ============================================================
add_library(glad STATIC third_party/glad/glad.c)
target_include_directories(glad PUBLIC third_party/glad/include)

# ============================================================
# ImGui library (compiled from source)
# ============================================================
add_library(imgui_lib STATIC
    ${imgui_SOURCE_DIR}/imgui.cpp
    ${imgui_SOURCE_DIR}/imgui_demo.cpp
    ${imgui_SOURCE_DIR}/imgui_draw.cpp
    ${imgui_SOURCE_DIR}/imgui_tables.cpp
    ${imgui_SOURCE_DIR}/imgui_widgets.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_glfw.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_opengl3.cpp
    # ImPlot
    ${implot_SOURCE_DIR}/implot.cpp
    ${implot_SOURCE_DIR}/implot_items.cpp
)
target_include_directories(imgui_lib PUBLIC
    ${imgui_SOURCE_DIR}
    ${imgui_SOURCE_DIR}/backends
    ${implot_SOURCE_DIR}
)
target_link_libraries(imgui_lib PUBLIC glfw glad)
target_compile_definitions(imgui_lib PUBLIC IMGUI_IMPL_OPENGL_LOADER_GLAD)

# ============================================================
# KooViewer executable
# ============================================================
set(VIEWER_SOURCES
    src/main.cpp
    src/app/App.cpp
    src/app/DeepReportApp.cpp
    src/gpu/Shader.cpp
    src/gpu/MeshGPU.cpp
    src/scene/Camera.cpp
    src/data/SimData.cpp
    src/data/ReportData.cpp
    src/widgets/VideoPlayer.cpp
)

add_executable(koo_viewer ${VIEWER_SOURCES})

target_include_directories(koo_viewer PRIVATE
    src
    ${CMAKE_SOURCE_DIR}/include   # kood3plot headers
)

target_link_libraries(koo_viewer PRIVATE
    imgui_lib
    kood3plot          # core reader + analysis
    glad
    glfw
    nlohmann_json::nlohmann_json
)

# Platform-specific GL linking
if(UNIX AND NOT APPLE)
    target_link_libraries(koo_viewer PRIVATE GL dl pthread)
elseif(APPLE)
    target_link_libraries(koo_viewer PRIVATE "-framework OpenGL")
endif()

# OpenMP for fringe computation
find_package(OpenMP)
if(OpenMP_CXX_FOUND)
    target_link_libraries(koo_viewer PRIVATE OpenMP::OpenMP_CXX)
endif()

install(TARGETS koo_viewer RUNTIME DESTINATION bin)
