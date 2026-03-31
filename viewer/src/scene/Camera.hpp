#pragma once
#include <cmath>
#include <cstring>
#include <algorithm>

struct Camera {
    // Orbit angles (radians)
    float yaw = 0.4f;
    float pitch = 0.3f;
    float distance = 5.0f;

    // Pan offset
    float panX = 0.0f, panY = 0.0f;

    // Target center
    float cx = 0.0f, cy = 0.0f, cz = 0.0f;

    // Projection
    float fov = 45.0f;
    float nearPlane = 0.01f;
    float farPlane = 1000.0f;
    float aspect = 1.0f;

    // Matrices (column-major for OpenGL)
    float view[16]{};
    float proj[16]{};
    float mvp[16]{};
    float normalMat[9]{};

    void fitTo(float minX, float minY, float minZ, float maxX, float maxY, float maxZ) {
        cx = (minX + maxX) * 0.5f;
        cy = (minY + maxY) * 0.5f;
        cz = (minZ + maxZ) * 0.5f;
        float dx = maxX - minX, dy = maxY - minY, dz = maxZ - minZ;
        float diag = std::sqrt(dx*dx + dy*dy + dz*dz);
        distance = diag * 1.2f;
        nearPlane = diag * 0.001f;
        farPlane = diag * 10.0f;
        panX = panY = 0.0f;
    }

    void orbit(float dYaw, float dPitch) {
        yaw += dYaw;
        pitch = std::clamp(pitch + dPitch, -1.5f, 1.5f);
    }

    void pan(float dx, float dy) {
        panX += dx * distance * 0.001f;
        panY += dy * distance * 0.001f;
    }

    void zoom(float factor) {
        distance *= factor;
        distance = std::max(nearPlane * 2.0f, distance);
    }

    void update() {
        float cp = cosf(pitch), sp = sinf(pitch);
        float cy_ = cosf(yaw), sy = sinf(yaw);

        float eyeX = cx + distance * cp * sy + panX;
        float eyeY = cy + distance * sp + panY;
        float eyeZ = cz + distance * cp * cy_;

        // View matrix (lookAt)
        float fx = cx + panX - eyeX, fy = cy + panY - eyeY, fz = cz - eyeZ;
        float fl = sqrtf(fx*fx + fy*fy + fz*fz);
        fx /= fl; fy /= fl; fz /= fl;

        float ux = 0, uy = 1, uz = 0;
        float sx = fy*uz - fz*uy, sy_ = fz*ux - fx*uz, sz = fx*uy - fy*ux;
        float sl = sqrtf(sx*sx + sy_*sy_ + sz*sz);
        if (sl > 1e-6f) { sx /= sl; sy_ /= sl; sz /= sl; }

        ux = sy_*fz - sz*fy; uy = sz*fx - sx*fz; uz = sx*fy - sy_*fx;

        float tx = -(sx*eyeX + sy_*eyeY + sz*eyeZ);
        float ty = -(ux*eyeX + uy*eyeY + uz*eyeZ);
        float tz = -(-fx*eyeX + -fy*eyeY + -fz*eyeZ);

        view[0]=sx;  view[4]=sy_; view[8]=sz;   view[12]=tx;
        view[1]=ux;  view[5]=uy;  view[9]=uz;   view[13]=ty;
        view[2]=-fx; view[6]=-fy; view[10]=-fz; view[14]=tz;
        view[3]=0;   view[7]=0;   view[11]=0;   view[15]=1;

        // Perspective projection
        float f = 1.0f / tanf(fov * 3.14159f / 360.0f);
        float nf = 1.0f / (nearPlane - farPlane);
        std::memset(proj, 0, sizeof(proj));
        proj[0] = f / aspect;
        proj[5] = f;
        proj[10] = (farPlane + nearPlane) * nf;
        proj[11] = -1.0f;
        proj[14] = 2.0f * farPlane * nearPlane * nf;

        // MVP = proj * view
        for (int i = 0; i < 4; ++i)
            for (int j = 0; j < 4; ++j) {
                mvp[i + j*4] = 0;
                for (int k = 0; k < 4; ++k)
                    mvp[i + j*4] += proj[i + k*4] * view[k + j*4];
            }

        // Normal matrix (upper-left 3x3 of view, transposed inverse)
        normalMat[0]=view[0]; normalMat[1]=view[1]; normalMat[2]=view[2];
        normalMat[3]=view[4]; normalMat[4]=view[5]; normalMat[5]=view[6];
        normalMat[6]=view[8]; normalMat[7]=view[9]; normalMat[8]=view[10];
    }
};
