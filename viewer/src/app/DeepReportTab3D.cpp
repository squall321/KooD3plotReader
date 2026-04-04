#include "app/DeepReportApp.hpp"
#include "app/DeepReportColors.hpp"
#include <imgui.h>
#include <implot.h>
#include <algorithm>
#include <cstdio>
#include <cmath>
#include <string>
#include <iostream>

// ============================================================
// 3D Viewer — shaders + colormap (private to this TU)
// ============================================================
// Mesh shader — supports GL clip plane for section view
static const char* VERT3D = R"(
#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aNorm;
layout(location=2) in float aFringe;
uniform mat4  uMVP;
uniform mat3  uNormalMat;
uniform int   uSectionEnabled;
uniform int   uSectionAxis;   // 0=X 1=Y 2=Z
uniform float uSectionPos;    // world coordinate of cut plane
out vec3  vNorm;
out float vFringe;
void main() {
    gl_Position = uMVP * vec4(aPos, 1.0);
    vNorm   = normalize(uNormalMat * aNorm);
    vFringe = aFringe;
    // Keep vertices on the negative side of the cut plane (coord < cutPos)
    float coord = (uSectionAxis == 0) ? aPos.x
                : (uSectionAxis == 1) ? aPos.y
                :                       aPos.z;
    gl_ClipDistance[0] = (uSectionEnabled == 1) ? (uSectionPos - coord) : 1.0;
}
)";

static const char* FRAG3D = R"(
#version 330 core
in vec3 vNorm;
in float vFringe;
uniform sampler1D uColormap;
uniform vec3  uLightDir;
uniform float uAmbient;
uniform int   uUseFringe;
uniform vec3  uFlatColor;
out vec4 fragColor;
void main() {
    vec3 color;
    if (uUseFringe == 1)
        color = texture(uColormap, clamp(vFringe, 0.0, 1.0)).rgb;
    else
        color = uFlatColor;
    vec3 N = normalize(vNorm);
    float diff = abs(dot(N, uLightDir));
    color *= uAmbient + (1.0 - uAmbient) * diff;
    fragColor = vec4(color, 1.0);
}
)";

// Flat-color shader for the cut plane indicator quad
static const char* VERT_PLANE = R"(
#version 330 core
layout(location=0) in vec3 aPos;
uniform mat4 uMVP;
void main() { gl_Position = uMVP * vec4(aPos, 1.0); }
)";

static const char* FRAG_PLANE = R"(
#version 330 core
uniform vec4 uColor;
out vec4 fragColor;
void main() { fragColor = uColor; }
)";

static void buildJetColormap(unsigned char* data) {
    for (int i = 0; i < 256; ++i) {
        float t = i / 255.0f;
        float r, g, b;
        if (t < 0.25f)      { r = 0; g = t/0.25f; b = 1; }
        else if (t < 0.5f)  { r = 0; g = 1; b = 1-(t-0.25f)/0.25f; }
        else if (t < 0.75f) { r = (t-0.5f)/0.25f; g = 1; b = 0; }
        else                { r = 1; g = 1-(t-0.75f)/0.25f; b = 0; }
        data[i*3+0] = (unsigned char)(r*255);
        data[i*3+1] = (unsigned char)(g*255);
        data[i*3+2] = (unsigned char)(b*255);
    }
}

void DeepReportApp::init3DViewer() {
    if (data_.d3plot_path.empty()) return;
    if (!sim3d_.loadMesh(data_.d3plot_path)) {
        std::cout << "[3D] Failed to load mesh: " << sim3d_.loadError << "\n";
        return;
    }
    std::cout << "[3D] Mesh: " << sim3d_.mesh.nodes.size() << " nodes, "
              << sim3d_.extFaces.size() << " exterior faces\n";

    sim3d_.loadStatesAsync(data_.d3plot_path, 4);

    shader3d_.loadFromString(VERT3D, FRAG3D);

    // Colormap texture
    glGenTextures(1, &colormapTex_);
    glBindTexture(GL_TEXTURE_1D, colormapTex_);
    unsigned char cmapData[256*3];
    buildJetColormap(cmapData);
    glTexImage1D(GL_TEXTURE_1D, 0, GL_RGB, 256, 0, GL_RGB, GL_UNSIGNED_BYTE, cmapData);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);

    auto gpuFaces = sim3d_.buildGPUFaces();
    meshGPU_.build(sim3d_.initialCoords, gpuFaces);

    camera3d_.fitTo(meshGPU_.bboxMin[0], meshGPU_.bboxMin[1], meshGPU_.bboxMin[2],
                    meshGPU_.bboxMax[0], meshGPU_.bboxMax[1], meshGPU_.bboxMax[2]);

    // Cut plane indicator: flat-color shader + dynamic quad VAO
    shaderPlane_.loadFromString(VERT_PLANE, FRAG_PLANE);
    glGenVertexArrays(1, &planeVAO_);
    glGenBuffers(1, &planeVBO_);
    glBindVertexArray(planeVAO_);
    glBindBuffer(GL_ARRAY_BUFFER, planeVBO_);
    glBufferData(GL_ARRAY_BUFFER, 4 * 3 * sizeof(float), nullptr, GL_DYNAMIC_DRAW);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, nullptr);
    glEnableVertexAttribArray(0);
    glBindVertexArray(0);

    mesh3dReady_ = true;
}

void DeepReportApp::ensureFBO(int w, int h) {
    if (w == fboW_ && h == fboH_ && fbo3d_) return;
    if (fbo3d_) { glDeleteFramebuffers(1, &fbo3d_); glDeleteTextures(1, &fboTex3d_); glDeleteRenderbuffers(1, &fboDepth3d_); }

    fboW_ = w; fboH_ = h;
    glGenFramebuffers(1, &fbo3d_);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo3d_);

    glGenTextures(1, &fboTex3d_);
    glBindTexture(GL_TEXTURE_2D, fboTex3d_);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, fboTex3d_, 0);

    glGenRenderbuffers(1, &fboDepth3d_);
    glBindRenderbuffer(GL_RENDERBUFFER, fboDepth3d_);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, w, h);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, fboDepth3d_);

    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}

void DeepReportApp::setPresetView(int axis) {
    camera3d_.fitTo(meshGPU_.bboxMin[0], meshGPU_.bboxMin[1], meshGPU_.bboxMin[2],
                    meshGPU_.bboxMax[0], meshGPU_.bboxMax[1], meshGPU_.bboxMax[2]);
    constexpr float PI = 3.14159265f;
    switch (axis) {
        case 0: camera3d_.yaw = 0;       camera3d_.pitch = 0;      break;  // Front (-Z)
        case 1: camera3d_.yaw = PI;      camera3d_.pitch = 0;      break;  // Back (+Z)
        case 2: camera3d_.yaw = PI/2;    camera3d_.pitch = 0;      break;  // Right (+X)
        case 3: camera3d_.yaw = -PI/2;   camera3d_.pitch = 0;      break;  // Left (-X)
        case 4: camera3d_.yaw = 0;       camera3d_.pitch = PI/2-0.01f; break; // Top (+Y)
        case 5: camera3d_.yaw = 0;       camera3d_.pitch = -PI/2+0.01f; break; // Bottom (-Y)
    }
}

void DeepReportApp::render3DTab() {
    // Lazy init
    if (!mesh3dReady_ && !data_.d3plot_path.empty()) {
        static bool initAttempted = false;
        if (!initAttempted) {
            initAttempted = true;
            init3DViewer();
        }
    }

    if (!mesh3dReady_) {
        ImGui::TextColored(COL_DIM, "No d3plot path in result data (need result.json with d3plot_path)");
        ImGui::TextColored(COL_DIM, "Path: %s", data_.d3plot_path.c_str());
        return;
    }

    // Controls row — preset views
    const char* viewNames[] = {"Front", "Back", "Right", "Left", "Top", "Bottom"};
    for (int i = 0; i < 6; ++i) {
        if (i > 0) ImGui::SameLine();
        if (ImGui::Button(viewNames[i])) setPresetView(i);
    }
    ImGui::SameLine();
    ImGui::Checkbox("Fringe", &show3DFringe_);
    ImGui::SameLine();
    ImGui::Checkbox("Wire", &wireframe3d_);

    // Section view controls
    ImGui::SameLine();
    ImGui::Separator();
    ImGui::SameLine();
    ImGui::Checkbox("Section", &section3DEnabled_);
    if (section3DEnabled_) {
        ImGui::SameLine();
        ImGui::TextColored(COL_DIM, "|");
        ImGui::SameLine();
        ImGui::RadioButton("X", &section3DAxis_, 0); ImGui::SameLine();
        ImGui::RadioButton("Y", &section3DAxis_, 1); ImGui::SameLine();
        ImGui::RadioButton("Z", &section3DAxis_, 2); ImGui::SameLine();
        ImGui::SetNextItemWidth(200);
        ImGui::SliderFloat("##secpos", &section3DPos_, 0.0f, 1.0f, "");
        // Show world coordinate
        float bmin = meshGPU_.bboxMin[section3DAxis_];
        float bmax = meshGPU_.bboxMax[section3DAxis_];
        float worldPos = bmin + section3DPos_ * (bmax - bmin);
        const char* axName = (section3DAxis_ == 0) ? "X" : (section3DAxis_ == 1) ? "Y" : "Z";
        ImGui::SameLine();
        ImGui::TextColored(COL_ACCENT, "%s = %.3f", axName, worldPos);
    }

    if (sim3d_.statesLoaded && sim3d_.numStates() > 0) {
        ImGui::SameLine();
        if (ImGui::Button(playing3d_ ? "Pause" : "Play")) playing3d_ = !playing3d_;
        ImGui::SameLine();
        ImGui::SetNextItemWidth(200);
        ImGui::SliderInt("##state3d", &current3DState_, 0, sim3d_.numStates() - 1);
        ImGui::SameLine();
        ImGui::Text("t=%.6f", sim3d_.stateTime(current3DState_));

        // Playback
        if (playing3d_) {
            playTimer3d_ += ImGui::GetIO().DeltaTime;
            if (playTimer3d_ > 1.0f / 30.0f) {
                playTimer3d_ = 0;
                current3DState_ = (current3DState_ + 1) % sim3d_.numStates();
            }
        }

        // Update mesh
        auto coords = sim3d_.getDeformedCoords(current3DState_);
        std::vector<float> fringe;
        if (show3DFringe_) fringe = sim3d_.getVonMisesFringe(current3DState_);
        meshGPU_.updatePositions(coords, fringe);
    } else if (!sim3d_.statesLoaded) {
        ImGui::SameLine();
        ImGui::TextColored(COL_DIM, "Loading states...");
    }

    // Render to FBO
    ImVec2 avail = ImGui::GetContentRegionAvail();
    int vpW = std::max(100, (int)avail.x);
    int vpH = std::max(100, (int)avail.y);
    ensureFBO(vpW, vpH);

    // Mouse interaction on viewport
    ImVec2 vpPos = ImGui::GetCursorScreenPos();
    ImGui::InvisibleButton("##3dvp", avail);
    bool vpHovered = ImGui::IsItemHovered();

    if (vpHovered) {
        ImGuiIO& io = ImGui::GetIO();
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Left)) {
            ImVec2 d = io.MouseDelta;
            camera3d_.orbit(-d.x * 0.005f, -d.y * 0.005f);
        }
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Middle)) {
            ImVec2 d = io.MouseDelta;
            camera3d_.pan(-d.x, d.y);
        }
        if (io.MouseWheel != 0)
            camera3d_.zoom(io.MouseWheel > 0 ? 0.9f : 1.1f);
    }

    camera3d_.aspect = (float)vpW / vpH;
    camera3d_.update();

    // Compute section world position
    float sectionWorldPos = 0.0f;
    if (section3DEnabled_) {
        float bmin = meshGPU_.bboxMin[section3DAxis_];
        float bmax = meshGPU_.bboxMax[section3DAxis_];
        sectionWorldPos = bmin + section3DPos_ * (bmax - bmin);
    }

    // Render to FBO
    glBindFramebuffer(GL_FRAMEBUFFER, fbo3d_);
    glViewport(0, 0, vpW, vpH);
    glClearColor(0.08f, 0.08f, 0.14f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    glEnable(GL_DEPTH_TEST);

    if (section3DEnabled_) glEnable(GL_CLIP_DISTANCE0);

    if (wireframe3d_) glPolygonMode(GL_FRONT_AND_BACK, GL_LINE);

    shader3d_.use();
    shader3d_.setMat4("uMVP", camera3d_.mvp);
    shader3d_.setMat3("uNormalMat", camera3d_.normalMat);
    shader3d_.setVec3("uLightDir", 0.3f, 0.8f, 0.5f);
    shader3d_.setFloat("uAmbient", 0.3f);
    shader3d_.setInt("uUseFringe", show3DFringe_ ? 1 : 0);
    shader3d_.setInt("uSectionEnabled", section3DEnabled_ ? 1 : 0);
    shader3d_.setInt("uSectionAxis", section3DAxis_);
    shader3d_.setFloat("uSectionPos", sectionWorldPos);

    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_1D, colormapTex_);
    shader3d_.setInt("uColormap", 0);

    for (size_t i = 0; i < meshGPU_.partCount(); ++i) {
        const auto& p = meshGPU_.part(i);
        if (!p.visible) continue;
        if (!show3DFringe_)
            shader3d_.setVec3("uFlatColor", p.color[0], p.color[1], p.color[2]);
        glBindVertexArray(p.vao);
        glDrawElements(GL_TRIANGLES, p.indexCount, GL_UNSIGNED_INT, nullptr);
    }

    if (wireframe3d_) glPolygonMode(GL_FRONT_AND_BACK, GL_FILL);

    if (section3DEnabled_) {
        glDisable(GL_CLIP_DISTANCE0);

        // Build cut plane quad vertices spanning the model bbox
        float ext = 0.02f;  // 2% extension beyond bbox for visibility
        float x0 = meshGPU_.bboxMin[0] - ext * (meshGPU_.bboxMax[0] - meshGPU_.bboxMin[0]);
        float x1 = meshGPU_.bboxMax[0] + ext * (meshGPU_.bboxMax[0] - meshGPU_.bboxMin[0]);
        float y0 = meshGPU_.bboxMin[1] - ext * (meshGPU_.bboxMax[1] - meshGPU_.bboxMin[1]);
        float y1 = meshGPU_.bboxMax[1] + ext * (meshGPU_.bboxMax[1] - meshGPU_.bboxMin[1]);
        float z0 = meshGPU_.bboxMin[2] - ext * (meshGPU_.bboxMax[2] - meshGPU_.bboxMin[2]);
        float z1 = meshGPU_.bboxMax[2] + ext * (meshGPU_.bboxMax[2] - meshGPU_.bboxMin[2]);
        float p = sectionWorldPos;
        float quad[4][3];
        if (section3DAxis_ == 0) {  // X plane
            quad[0][0]=p; quad[0][1]=y0; quad[0][2]=z0;
            quad[1][0]=p; quad[1][1]=y1; quad[1][2]=z0;
            quad[2][0]=p; quad[2][1]=y1; quad[2][2]=z1;
            quad[3][0]=p; quad[3][1]=y0; quad[3][2]=z1;
        } else if (section3DAxis_ == 1) {  // Y plane
            quad[0][0]=x0; quad[0][1]=p; quad[0][2]=z0;
            quad[1][0]=x1; quad[1][1]=p; quad[1][2]=z0;
            quad[2][0]=x1; quad[2][1]=p; quad[2][2]=z1;
            quad[3][0]=x0; quad[3][1]=p; quad[3][2]=z1;
        } else {                            // Z plane
            quad[0][0]=x0; quad[0][1]=y0; quad[0][2]=p;
            quad[1][0]=x1; quad[1][1]=y0; quad[1][2]=p;
            quad[2][0]=x1; quad[2][1]=y1; quad[2][2]=p;
            quad[3][0]=x0; quad[3][1]=y1; quad[3][2]=p;
        }
        glBindBuffer(GL_ARRAY_BUFFER, planeVBO_);
        glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof(quad), quad);

        shaderPlane_.use();
        shaderPlane_.setMat4("uMVP", camera3d_.mvp);
        glBindVertexArray(planeVAO_);

        // Semi-transparent fill
        glEnable(GL_BLEND);
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
        glDepthMask(GL_FALSE);
        glUniform4f(glGetUniformLocation(shaderPlane_.id, "uColor"),
                    0.25f, 0.65f, 1.0f, 0.18f);
        glDrawArrays(GL_TRIANGLE_FAN, 0, 4);

        // Opaque outline
        glUniform4f(glGetUniformLocation(shaderPlane_.id, "uColor"),
                    0.25f, 0.75f, 1.0f, 0.85f);
        glLineWidth(1.5f);
        glDrawArrays(GL_LINE_LOOP, 0, 4);
        glLineWidth(1.0f);

        glDepthMask(GL_TRUE);
        glDisable(GL_BLEND);
        glBindVertexArray(0);
    }

    glBindFramebuffer(GL_FRAMEBUFFER, 0);

    // Draw FBO texture as ImGui image
    ImGui::SetCursorScreenPos(vpPos);
    ImGui::Image((ImTextureID)(intptr_t)fboTex3d_, avail, ImVec2(0,1), ImVec2(1,0));
}

