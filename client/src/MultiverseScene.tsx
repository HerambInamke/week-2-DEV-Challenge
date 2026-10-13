import { useEffect, useRef } from "react"
import * as THREE from "three"
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js"
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js"
import { RenderPass } from "three/addons/postprocessing/RenderPass.js"
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js"
import { OutputPass } from "three/addons/postprocessing/OutputPass.js"

type Props = {
  selected: number | null
  hovered: number | null
  loading: boolean
  onReady: (ready: boolean) => void
}

export default function MultiverseScene({
  selected,
  hovered,
  loading,
  onReady,
}: Props) {
  const host = useRef<HTMLDivElement>(null)
  const state = useRef({ selected, hovered, loading })
  state.current = { selected, hovered, loading }

  useEffect(() => {
    const element = host.current
    if (!element) return
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
      })
    } catch {
      onReady(false)
      return
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6))
    renderer.setClearColor(0x11151c, 0)
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 0.84
    renderer.domElement.setAttribute("aria-hidden", "true")
    element.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(43, 1, 0.1, 80)
    camera.position.set(0, 0.3, 13)
    const pmrem = new THREE.PMREMGenerator(renderer)
    const room = new RoomEnvironment()
    const environment = pmrem.fromScene(room, 0.04)
    scene.environment = environment.texture
    room.dispose()
    scene.add(new THREE.AmbientLight(0xd7e2ff, 0.82))
    const key = new THREE.DirectionalLight(0xf1f5ff, 2.7)
    key.position.set(-3, 6, 8)
    scene.add(key)
    const rim = new THREE.DirectionalLight(0x9facff, 0.8)
    rim.position.set(5, 1, -4)
    scene.add(rim)

    const glowCanvas = document.createElement("canvas")
    glowCanvas.width = glowCanvas.height = 128
    const context = glowCanvas.getContext("2d")!
    const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64)
    gradient.addColorStop(0, "rgba(255,255,255,.38)")
    gradient.addColorStop(0.2, "rgba(255,255,255,.12)")
    gradient.addColorStop(1, "rgba(255,255,255,0)")
    context.fillStyle = gradient
    context.fillRect(0, 0, 128, 128)
    const glowTexture = new THREE.CanvasTexture(glowCanvas)
    const colors = [0x83c9a8, 0x9480cf, 0x72b5ca]
    const positions = [
      new THREE.Vector3(-2.9, 0.8, 0),
      new THREE.Vector3(0.2, 2.1, -1),
      new THREE.Vector3(3.1, -0.45, 0.35),
    ]
    const portals: THREE.Group[] = []
    const cores: THREE.Mesh[] = []
    const rings: THREE.Mesh<THREE.TorusGeometry, THREE.MeshStandardMaterial>[] =
      []
    const paths: THREE.Mesh<THREE.TubeGeometry, THREE.MeshBasicMaterial>[] = []
    const auras: THREE.Sprite[] = []
    const origin = new THREE.Vector3(0.2, -2.6, 1)

    positions.forEach((position, i) => {
      const world = new THREE.Group()
      world.position.copy(position)
      world.rotation.set(0.12, [0.3, -0.23, -0.36][i], [-0.25, 0.2, 0.27][i])
      scene.add(world)
      portals.push(world)
      const metal = new THREE.MeshPhysicalMaterial({
        color: colors[i],
        metalness: 0.8,
        roughness: 0.2,
        clearcoat: 1,
        clearcoatRoughness: 0.12,
      })
      const torus = new THREE.Mesh(
        new THREE.TorusGeometry(1.25, 0.095, 24, 128),
        metal,
      )
      world.add(torus)
      const glowMaterial = new THREE.MeshStandardMaterial({
        color: colors[i],
        emissive: colors[i],
        emissiveIntensity: 1.25,
        roughness: 0.2,
        metalness: 0.35,
      })
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(1.17, 0.017, 12, 128),
        glowMaterial,
      )
      ring.position.z = 0.065
      world.add(ring)
      rings.push(ring)
      const outerRing = new THREE.Mesh(
        new THREE.TorusGeometry(1.34, 0.008, 8, 128),
        new THREE.MeshBasicMaterial({
          color: colors[i],
          transparent: true,
          opacity: 0.5,
        }),
      )
      outerRing.position.z = -0.065
      world.add(outerRing)
      const glass = new THREE.MeshPhysicalMaterial({
        color: colors[i],
        metalness: 0.05,
        roughness: 0.13,
        transmission: 0.62,
        thickness: 0.6,
        ior: 1.45,
        transparent: true,
        opacity: 0.88,
        side: THREE.DoubleSide,
        envMapIntensity: 0.9,
      })
      const pane = new THREE.Mesh(new THREE.CircleGeometry(1.13, 80), glass)
      pane.position.z = -0.11
      world.add(pane)
      // Nested contours create depth behind the refractive portal face.
      for (let j = 0; j < 7; j++) {
        const contour = new THREE.Mesh(
          new THREE.TorusGeometry(1.08 - j * 0.115, 0.005, 6, 80),
          new THREE.MeshBasicMaterial({
            color: colors[i],
            transparent: true,
            opacity: 0.27 - j * 0.025,
          }),
        )
        contour.position.z = -0.2 - j * 0.14
        world.add(contour)
      }
      const geometry =
        i === 0
          ? new THREE.OctahedronGeometry(0.52)
          : i === 1
            ? new THREE.IcosahedronGeometry(0.49)
            : new THREE.TetrahedronGeometry(0.66)
      const core = new THREE.Mesh(
        geometry,
        new THREE.MeshPhysicalMaterial({
          color: colors[i],
          metalness: 0.35,
          roughness: 0.08,
          transmission: 0.45,
          thickness: 1.2,
          ior: 1.6,
          clearcoat: 1,
          emissive: colors[i],
          emissiveIntensity: 0.18,
        }),
      )
      core.position.z = 0.18
      world.add(core)
      cores.push(core)
      const edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(geometry),
        new THREE.LineBasicMaterial({
          color: colors[i],
          transparent: true,
          opacity: 0.6,
        }),
      )
      core.add(edges)
      for (let j = 0; j < 5; j++) {
        const shard = new THREE.Mesh(
          new THREE.OctahedronGeometry(0.06 + j * 0.015),
          metal,
        )
        const angle = (j / 5) * Math.PI * 2
        shard.position.set(
          Math.cos(angle) * 0.83,
          Math.sin(angle) * 0.83,
          0.07 + j * 0.04,
        )
        shard.rotation.set(j, j * 0.6, j * 0.8)
        world.add(shard)
      }
      const aura = new THREE.Sprite(
        new THREE.SpriteMaterial({
          map: glowTexture,
          color: colors[i],
          transparent: true,
          opacity: 0.22,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        }),
      )
      aura.scale.set(4.8, 4.8, 1)
      aura.position.copy(position).add(new THREE.Vector3(0, 0, -0.8))
      scene.add(aura)
      auras.push(aura)
      const point = new THREE.PointLight(colors[i], 2.2, 5.5, 2)
      point.position.copy(position).add(new THREE.Vector3(0, 0, 1.5))
      scene.add(point)
      const curve = new THREE.CatmullRomCurve3([
        origin.clone(),
        new THREE.Vector3(position.x * 0.3, -1.9, 0.8),
        new THREE.Vector3(position.x * 0.85, position.y - 1.8, -0.4),
        position.clone().add(new THREE.Vector3(0, -1.3, 0)),
      ])
      const tube = new THREE.Mesh(
        new THREE.TubeGeometry(curve, 100, 0.013, 6, false),
        new THREE.MeshBasicMaterial({
          color: colors[i],
          transparent: true,
          opacity: 0.5,
        }),
      )
      scene.add(tube)
      paths.push(tube)
    })

    const originMesh = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.2),
      new THREE.MeshStandardMaterial({
        color: 0xd5ffe9,
        emissive: 0xa9eacc,
        emissiveIntensity: 0.48,
        metalness: 0.5,
        roughness: 0.1,
      }),
    )
    originMesh.position.copy(origin)
    scene.add(originMesh)
    const particlePositions = new Float32Array(240 * 3)
    for (let i = 0; i < 240; i++) {
      particlePositions[i * 3] = Math.sin(i * 127.1) * 6
      particlePositions[i * 3 + 1] = Math.cos(i * 73.3) * 4
      particlePositions[i * 3 + 2] = Math.sin(i * 37.7) * 3 - 1
    }
    const particleGeometry = new THREE.BufferGeometry()
    particleGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(particlePositions, 3),
    )
    const particles = new THREE.Points(
      particleGeometry,
      new THREE.PointsMaterial({
        color: 0xc9ddf1,
        map: glowTexture,
        size: 0.055,
        transparent: true,
        opacity: 0.7,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    )
    scene.add(particles)
    const composer = new EffectComposer(renderer)
    composer.addPass(new RenderPass(scene, camera))
    const bloom = new UnrealBloomPass(
      new THREE.Vector2(800, 700),
      0.32,
      0.48,
      1.12,
    )
    composer.addPass(bloom)
    composer.addPass(new OutputPass())
    const resize = () => {
      const { width, height } = element.getBoundingClientRect()
      if (!width || !height) return
      renderer.setSize(width, height)
      composer.setSize(width, height)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(element)
    resize()
    const media = window.matchMedia("(prefers-reduced-motion: reduce)")
    let reduced = media.matches
    const onMotion = () => {
      reduced = media.matches
    }
    media.addEventListener("change", onMotion)
    let visible = true
    const intersection = new IntersectionObserver((entries) => {
      visible = entries[0].isIntersecting
    })
    intersection.observe(element)
    let frame = 0
    let previous = performance.now()
    let elapsed = 0
    let loadingStart = 0
    let wasLoading = false
    const lookAt = new THREE.Vector3(0, 0.1, 0)
    const targetPosition = new THREE.Vector3()
    const targetLook = new THREE.Vector3()
    const animate = (now: number) => {
      frame = requestAnimationFrame(animate)
      const dt = Math.min((now - previous) / 1000, 0.05)
      previous = now
      if (!visible || document.hidden) return
      if (!reduced) elapsed += dt
      const current = state.current
      if (current.loading && !wasLoading) loadingStart = now
      wasLoading = current.loading
      const progress = current.loading
        ? Math.min((now - loadingStart) / 1600, 1)
        : 1
      const travel =
        current.loading && !reduced ? Math.sin(progress * Math.PI) : 0
      targetPosition.set(travel * 0.4, 0.3 + travel * 0.35, 13 - travel * 2.1)
      targetLook.set(0, 0.1, 0)
      if (current.selected !== null) {
        const position = positions[current.selected]
        targetPosition.set(position.x * 0.72, position.y * 0.72, 8.6)
        targetLook.copy(position).multiplyScalar(0.7)
      }
      const ease = reduced ? 1 : 1 - Math.exp(-dt * 4.2)
      camera.position.lerp(targetPosition, ease)
      lookAt.lerp(targetLook, ease)
      camera.lookAt(lookAt)
      portals.forEach((portal, i) => {
        portal.position.y =
          positions[i].y + Math.sin(elapsed * 0.65 + i * 2) * 0.085
        const active = current.hovered === i || current.selected === i
        portal.position.z = THREE.MathUtils.lerp(
          portal.position.z,
          positions[i].z + (active ? 1.15 : 0),
          1 - Math.exp(-dt * 5),
        )
        rings[i].material.emissiveIntensity = THREE.MathUtils.lerp(
          rings[i].material.emissiveIntensity,
          active ? 1.55 : 0.72,
          ease,
        )
        auras[i].material.opacity = active ? 0.3 : 0.14
        cores[i].rotation.set(
          elapsed * 0.17 + i,
          elapsed * 0.23,
          elapsed * 0.08,
        )
        paths[i].material.opacity = active ? 0.72 : 0.32
        const count = paths[i].geometry.index!.count
        paths[i].geometry.setDrawRange(
          0,
          reduced
            ? count
            : Math.floor(
                (count *
                  Math.max(0, Math.min(1, (progress - i * 0.08) / 0.75))) /
                  3,
              ) * 3,
        )
      })
      originMesh.rotation.y = elapsed * 0.35
      originMesh.scale.setScalar(current.loading ? 1 + travel * 0.7 : 1)
      particles.rotation.z = elapsed * 0.007
      composer.render()
    }
    frame = requestAnimationFrame(animate)
    onReady(true)
    const onLost = (event: Event) => {
      event.preventDefault()
      onReady(false)
    }
    renderer.domElement.addEventListener("webglcontextlost", onLost)
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      intersection.disconnect()
      media.removeEventListener("change", onMotion)
      renderer.domElement.removeEventListener("webglcontextlost", onLost)
      const materials = new Set<THREE.Material>()
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh
        mesh.geometry?.dispose()
        if (mesh.material)
          (Array.isArray(mesh.material)
            ? mesh.material
            : [mesh.material]
          ).forEach((material) => materials.add(material))
      })
      materials.forEach((material) => material.dispose())
      environment.dispose()
      pmrem.dispose()
      glowTexture.dispose()
      bloom.dispose()
      composer.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [onReady])

  return <div className="webgl-multiverse" ref={host} />
}
