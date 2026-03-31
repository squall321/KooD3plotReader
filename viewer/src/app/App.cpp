#include "app/App.hpp"
#include "gpu/Shader.hpp"
#include "gpu/MeshGPU.hpp"
#include "scene/Camera.hpp"
#include "data/SimData.hpp"

#include <glad/glad.h>
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_opengl3.h>
#include <implot.h>

#include <iostream>
#include <cstdio>

// Embedded shaders
static const char* VERT_SRC = R"(
#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNorm;
layout(location=2) in float aFringe;

uniform mat4 uMVP;
uniform mat3 uNormalMat;

out vec3 vNorm;
out float vFringe;

void main() {
    gl_Position = uMVP * vec4(aPos, 1.0);
    vNorm = normalize(uNormalMat * aNorm);
    vFringe = aFringe;
}
)";

static const char* FRAG_SRC = R"(
#version 330 core
in vec3 vNorm;
in float vFringe;

uniform sampler1D uColormap;
uniform vec3 uLightDir;
uniform float uAmbient;
uniform int uUseFringe;
uniform vec3 uFlatColor;

out vec4 fragColor;

void main() {
    vec3 color;
    if (uUseFringe == 1) {
        color = texture(uColormap, clamp(vFringe, 0.0, 1.0)).rgb;
    } else {
        color = uFlatColor;
    }
    vec3 N = normalize(vNorm);
    float diff = abs(dot(N, uLightDir));
    color *= uAmbient + (1.0 - uAmbient) * diff;
    fragColor = vec4(color, 1.0);
}
)";

// Jet colormap 256 texels
static void buildJetColormap(unsigned char* data) {
    for (int i = 0; i < 256; ++i) {
        float t = i / 255.0f;
        float r, g, b;
        if (t < 0.25f) {
            r = 0; g = t/0.25f; b = 1;
        } else if (t < 0.5f) {
            r = 0; g = 1; b = 1-(t-0.25f)/0.25f;
        } else if (t < 0.75f) {
            r = (t-0.5f)/0.25f; g = 1; b = 0;
        } else {
            r = 1; g = 1-(t-0.75f)/0.25f; b = 0;
        }
        data[i*3+0] = (unsigned char)(r*255);
        data[i*3+1] = (unsigned char)(g*255);
        data[i*3+2] = (unsigned char)(b*255);
    }
}

bool App::init(int width, int height, const char* title) {
    if (!glfwInit()) {
        std::cerr << "Failed to init GLFW\n";
        return false;
    }

    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
    glfwWindowHint(GLFW_SAMPLES, 4);

    window_ = glfwCreateWindow(width, height, title, nullptr, nullptr);
    if (!window_) {
        std::cerr << "Failed to create GLFW window\n";
        glfwTerminate();
        return false;
    }
    glfwMakeContextCurrent(window_);
    glfwSwapInterval(1);  // vsync

    if (!gladLoadGLLoader((GLADloadproc)glfwGetProcAddress)) {
        std::cerr << "Failed to init glad\n";
        return false;
    }

    // ImGui init
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImPlot::CreateContext();

    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;

    ImGui::StyleColorsDark();
    auto& style = ImGui::GetStyle();
    style.WindowRounding = 4.0f;
    style.FrameRounding = 3.0f;
    style.Colors[ImGuiCol_WindowBg] = ImVec4(0.10f, 0.11f, 0.15f, 1.0f);

    ImGui_ImplGlfw_InitForOpenGL(window_, true);
    ImGui_ImplOpenGL3_Init("#version 330");

    glEnable(GL_DEPTH_TEST);
    glEnable(GL_MULTISAMPLE);

    return true;
}

void App::run(const std::string& d3plotPath) {
    // Load data
    SimData sim;
    std::cout << "[KooViewer] Loading mesh: " << d3plotPath << "\n";
    if (!sim.loadMesh(d3plotPath)) {
        std::cerr << "Failed to load mesh: " << sim.loadError << "\n";
        return;
    }
    std::cout << "[KooViewer] Mesh: " << sim.mesh.nodes.size() << " nodes, "
              << sim.extFaces.size() << " exterior faces\n";

    // Start background state loading
    sim.loadStatesAsync(d3plotPath, 4);

    // Build GPU mesh
    Shader shader;
    if (!shader.loadFromString(VERT_SRC, FRAG_SRC)) {
        std::cerr << "Shader compile failed\n";
        return;
    }

    // Jet colormap texture
    GLuint cmapTex;
    glGenTextures(1, &cmapTex);
    glBindTexture(GL_TEXTURE_1D, cmapTex);
    unsigned char cmapData[256*3];
    buildJetColormap(cmapData);
    glTexImage1D(GL_TEXTURE_1D, 0, GL_RGB, 256, 0, GL_RGB, GL_UNSIGNED_BYTE, cmapData);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);

    MeshGPU meshGPU;
    auto gpuFaces = sim.buildGPUFaces();
    meshGPU.build(sim.initialCoords, gpuFaces);

    Camera camera;
    camera.fitTo(meshGPU.bboxMin[0], meshGPU.bboxMin[1], meshGPU.bboxMin[2],
                 meshGPU.bboxMax[0], meshGPU.bboxMax[1], meshGPU.bboxMax[2]);

    // State
    int currentState = 0;
    bool playing = false;
    bool useFringe = false;
    bool wireframe = false;
    float playTimer = 0.0f;
    float playFPS = 30.0f;

    while (!glfwWindowShouldClose(window_)) {
        glfwPollEvents();

        // Mouse input (when not captured by ImGui)
        ImGuiIO& io = ImGui::GetIO();
        if (!io.WantCaptureMouse) {
            if (ImGui::IsMouseDragging(ImGuiMouseButton_Left)) {
                ImVec2 d = ImGui::GetMouseDragDelta(ImGuiMouseButton_Left);
                camera.orbit(-d.x * 0.005f, -d.y * 0.005f);
                ImGui::ResetMouseDragDelta(ImGuiMouseButton_Left);
            }
            if (ImGui::IsMouseDragging(ImGuiMouseButton_Middle)) {
                ImVec2 d = ImGui::GetMouseDragDelta(ImGuiMouseButton_Middle);
                camera.pan(-d.x, d.y);
                ImGui::ResetMouseDragDelta(ImGuiMouseButton_Middle);
            }
            if (io.MouseWheel != 0) {
                camera.zoom(io.MouseWheel > 0 ? 0.9f : 1.1f);
            }
        }

        // Keyboard shortcuts
        if (!io.WantCaptureKeyboard) {
            if (ImGui::IsKeyPressed(ImGuiKey_R)) {
                camera.fitTo(meshGPU.bboxMin[0], meshGPU.bboxMin[1], meshGPU.bboxMin[2],
                             meshGPU.bboxMax[0], meshGPU.bboxMax[1], meshGPU.bboxMax[2]);
            }
            if (ImGui::IsKeyPressed(ImGuiKey_W)) wireframe = !wireframe;
            if (ImGui::IsKeyPressed(ImGuiKey_P) || ImGui::IsKeyPressed(ImGuiKey_Space)) playing = !playing;
        }

        // Playback
        if (playing && sim.statesLoaded) {
            playTimer += io.DeltaTime;
            if (playTimer > 1.0f / playFPS) {
                playTimer = 0;
                currentState = (currentState + 1) % sim.numStates();
            }
        }

        // Update camera
        int fbW, fbH;
        glfwGetFramebufferSize(window_, &fbW, &fbH);
        camera.aspect = fbW > 0 ? (float)fbW / fbH : 1.0f;
        camera.update();

        // Update mesh for current state
        if (sim.statesLoaded && sim.numStates() > 0) {
            auto coords = sim.getDeformedCoords(currentState);
            std::vector<float> fringe;
            if (useFringe) {
                fringe = sim.getVonMisesFringe(currentState);
            }
            meshGPU.updatePositions(coords, fringe);
        }

        // Render
        glViewport(0, 0, fbW, fbH);
        glClearColor(0.102f, 0.106f, 0.149f, 1.0f);  // #1a1b26
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        if (wireframe) glPolygonMode(GL_FRONT_AND_BACK, GL_LINE);

        shader.use();
        shader.setMat4("uMVP", camera.mvp);
        shader.setMat3("uNormalMat", camera.normalMat);
        shader.setVec3("uLightDir", 0.3f, 0.8f, 0.5f);
        shader.setFloat("uAmbient", 0.3f);
        shader.setInt("uUseFringe", useFringe ? 1 : 0);

        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_1D, cmapTex);
        shader.setInt("uColormap", 0);

        // Draw per part
        for (size_t i = 0; i < meshGPU.partCount(); ++i) {
            const auto& p = meshGPU.part(i);
            if (!p.visible) continue;
            if (!useFringe) {
                shader.setVec3("uFlatColor", p.color[0], p.color[1], p.color[2]);
            }
            glBindVertexArray(p.vao);
            glDrawElements(GL_TRIANGLES, p.indexCount, GL_UNSIGNED_INT, nullptr);
        }

        if (wireframe) glPolygonMode(GL_FRONT_AND_BACK, GL_FILL);

        // ImGui frame
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        // Control panel
        ImGui::SetNextWindowPos(ImVec2(10, 10), ImGuiCond_FirstUseEver);
        ImGui::SetNextWindowSize(ImVec2(300, 400), ImGuiCond_FirstUseEver);
        ImGui::Begin("Controls");

        ImGui::Text("Model: %zu nodes, %zu faces",
                     sim.mesh.nodes.size(), sim.extFaces.size());

        if (sim.statesLoaded) {
            ImGui::Text("States: %d", sim.numStates());
            ImGui::Separator();

            // Time slider
            ImGui::SliderInt("State", &currentState, 0,
                             std::max(0, sim.numStates() - 1));
            ImGui::Text("Time: %.6f", sim.stateTime(currentState));

            if (ImGui::Button(playing ? "Pause (P)" : "Play (P)")) playing = !playing;
            ImGui::SameLine();
            ImGui::SliderFloat("FPS", &playFPS, 1.0f, 60.0f);

            ImGui::Separator();
            ImGui::Checkbox("Von Mises Fringe", &useFringe);
        } else {
            ImGui::Text("Loading states...");
            ImGui::ProgressBar(0.5f);  // TODO: actual progress
        }

        ImGui::Separator();
        ImGui::Checkbox("Wireframe (W)", &wireframe);
        if (ImGui::Button("Reset View (R)")) {
            camera.fitTo(meshGPU.bboxMin[0], meshGPU.bboxMin[1], meshGPU.bboxMin[2],
                         meshGPU.bboxMax[0], meshGPU.bboxMax[1], meshGPU.bboxMax[2]);
        }

        ImGui::Separator();
        ImGui::Text("Parts:");
        for (size_t i = 0; i < meshGPU.partCount(); ++i) {
            auto& p = meshGPU.part(i);
            char label[64];
            snprintf(label, sizeof(label), "Part %d", p.partId);
            ImGui::Checkbox(label, &p.visible);
        }

        ImGui::End();

        ImGui::Render();
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());

        glfwSwapBuffers(window_);
    }

    glDeleteTextures(1, &cmapTex);
}

void App::shutdown() {
    ImPlot::DestroyContext();
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    if (window_) glfwDestroyWindow(window_);
    glfwTerminate();
}
