import * as THREE from "three";
import { ColladaLoader } from "three/examples/jsm/loaders/ColladaLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

export interface MeshLoadOptions {
  color?: [number, number, number];
}

export class MeshLoader {
  private collada = new ColladaLoader();
  private stl = new STLLoader();

  load(url: string, options: MeshLoadOptions = {}): Promise<THREE.Object3D> {
    const ext = url.split(".").pop()?.toLowerCase();
    if (ext === "dae") {
      return this.loadCollada(url, options);
    }
    if (ext === "stl") {
      return this.loadStl(url, options);
    }
    return Promise.reject(new Error(`Unsupported mesh format: ${ext}`));
  }

  private loadCollada(url: string, options: MeshLoadOptions): Promise<THREE.Object3D> {
    return new Promise((resolve, reject) => {
      this.collada.load(
        url,
        (collada) => {
          const model = collada.scene;
          const override = options.color;
          model.traverse((child) => {
            const mesh = child as THREE.Mesh;
            if (!mesh.isMesh || !mesh.material) {
              return;
            }
            const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
            const converted = materials.map((mat) => {
              if (
                (mat as THREE.Material & { isMeshBasicMaterial?: boolean }).isMeshBasicMaterial ||
                (mat as THREE.Material & { isMeshPhongMaterial?: boolean }).isMeshPhongMaterial ||
                (mat as THREE.Material & { isMeshLambertMaterial?: boolean }).isMeshLambertMaterial
              ) {
                return new THREE.MeshStandardMaterial({
                  color: (mat as THREE.MeshStandardMaterial).color ?? new THREE.Color(0.7, 0.7, 0.7),
                  map: (mat as THREE.MeshStandardMaterial).map ?? null,
                  side: (mat as THREE.MeshStandardMaterial).side ?? THREE.FrontSide,
                  transparent: (mat as THREE.MeshStandardMaterial).transparent ?? false,
                  opacity: (mat as THREE.MeshStandardMaterial).opacity ?? 1.0,
                  roughness: 0.7,
                  metalness: 0.2,
                });
              }
              return mat;
            });
            if (override) {
              const color = new THREE.Color(override[0], override[1], override[2]);
              converted.forEach((mat) => {
                if ((mat as THREE.MeshStandardMaterial).color) {
                  (mat as THREE.MeshStandardMaterial).color = color;
                }
              });
            }
            mesh.material = Array.isArray(mesh.material) ? converted : converted[0];
          });
          resolve(model);
        },
        undefined,
        (err) => reject(err ?? new Error(`Failed to load DAE: ${url}`))
      );
    });
  }

  private loadStl(url: string, options: MeshLoadOptions): Promise<THREE.Object3D> {
    return new Promise((resolve, reject) => {
      this.stl.load(
        url,
        (geometry) => {
          const c = options.color ?? [0.7, 0.7, 0.7];
          const material = new THREE.MeshStandardMaterial({
            color: new THREE.Color(c[0], c[1], c[2]),
            flatShading: true,
          });
          resolve(new THREE.Mesh(geometry, material));
        },
        undefined,
        (err) => reject(err ?? new Error(`Failed to load STL: ${url}`))
      );
    });
  }
}
