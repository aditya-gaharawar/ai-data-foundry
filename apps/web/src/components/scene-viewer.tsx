"use client";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { useWorkspace } from "./context";
import { ErrorNotice } from "./ui";

export default function SceneViewer({ path }: { path: string }) {
  const { organization } = useWorkspace();
  const host = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<unknown>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const target = host.current;
    if (!target) return;
    let renderer: THREE.WebGLRenderer | undefined;
    let controls: OrbitControls | undefined;
    let content: THREE.Group | undefined;
    let observer: ResizeObserver | undefined;
    let disposed = false;
    const abort = new AbortController();
    setError(null);
    setLoaded(false);
    function cleanupObject(object: THREE.Object3D) {
      object.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.geometry.dispose();
          const materials = Array.isArray(child.material)
            ? child.material
            : [child.material];
          for (const material of materials) {
            for (const value of Object.values(material))
              if (value instanceof THREE.Texture) value.dispose();
            material.dispose();
          }
        }
      });
    }
    async function load() {
      try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(target!.clientWidth, 320);
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.domElement.setAttribute("role", "img");
        renderer.domElement.setAttribute(
          "aria-label",
          "Interactive rendered scene. Drag to orbit, scroll to zoom, arrow keys to pan.",
        );
        renderer.domElement.tabIndex = 0;
        target!.appendChild(renderer.domElement);
        const scene = new THREE.Scene();
        scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 3));
        const light = new THREE.DirectionalLight(0xffffff, 3);
        light.position.set(4, 6, 5);
        scene.add(light);
        const camera = new THREE.PerspectiveCamera(
          45,
          target!.clientWidth / 320,
          0.01,
          1000,
        );
        controls = new OrbitControls(camera, renderer.domElement);
        controls.listenToKeyEvents(renderer.domElement);
        const response = await fetch(`/api${path}`, {
          headers: { "X-Organization-Id": organization.id },
          signal: abort.signal,
        });
        if (!response.ok)
          throw new Error("The protected scene artifact could not be loaded.");
        const bytes = await response.arrayBuffer();
        const checksum = Array.from(
          new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
        )
          .map((value) => value.toString(16).padStart(2, "0"))
          .join("");
        if (checksum !== response.headers.get("X-Content-SHA256"))
          throw new Error("Scene checksum verification failed.");
        const model = await new GLTFLoader().parseAsync(bytes, "");
        if (disposed) {
          cleanupObject(model.scene);
          return;
        }
        content = model.scene;
        scene.add(content);
        const bounds = new THREE.Box3().setFromObject(content);
        const center = bounds.getCenter(new THREE.Vector3());
        const size = bounds.getSize(new THREE.Vector3()).length();
        camera.position
          .copy(center)
          .add(new THREE.Vector3(1, 0.8, 1).multiplyScalar(size * 0.75));
        camera.lookAt(center);
        controls.target.copy(center);
        controls.update();
        const render = () => {
          if (!disposed) renderer?.render(scene, camera);
        };
        controls.addEventListener("change", render);
        observer = new ResizeObserver(() => {
          camera.aspect = target!.clientWidth / 320;
          camera.updateProjectionMatrix();
          renderer?.setSize(target!.clientWidth, 320);
          render();
        });
        observer.observe(target!);
        render();
        setLoaded(true);
      } catch (failure) {
        if (!disposed)
          setError(
            failure instanceof Error
              ? failure
              : new Error("3D preview unavailable in this browser."),
          );
      }
    }
    load();
    return () => {
      disposed = true;
      abort.abort();
      observer?.disconnect();
      controls?.dispose();
      if (content) cleanupObject(content);
      renderer?.dispose();
      renderer?.domElement.remove();
    };
  }, [path, organization.id]);
  return (
    <>
      <ErrorNotice error={error} />
      <div className="scene-preview" ref={host} />
      <p className="muted" role="status">
        {loaded
          ? "Verified GLB · drag to orbit, scroll to zoom, arrow keys to pan"
          : error
            ? "Use the rendered frame and object mask to inspect this scene."
            : "Loading protected 3D artifact…"}
      </p>
    </>
  );
}
