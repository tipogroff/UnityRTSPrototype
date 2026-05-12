using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

public static class Visual3BCharacterPreviewBuilder
{
    private const string FbxRoot = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX";
    private const string PrefabOutputDir = "Assets/Art/Prefabs/Visuals/Characters";
    private const string MaterialOutputPath = "Assets/Art/Materials/Preview_URP_Lit_Default.mat";
    private const string ScenePath = "Assets/Scenes/VisualPreview.unity";
    private const string ScreenshotDir = "Assets/Screenshots";

    private const float TargetCharacterHeight = 1.55f;
    private const float MaxFootprintSize = 0.85f;

    private sealed class Candidate
    {
        public string Group;
        public string FbxName;
        public string PreviewName;
        public float Yaw;
    }

    [MenuItem("Tools/Visual/Build Visual 3B Character Candidate Preview")]
    public static void BuildVisual3BCharacterPreview()
    {
        AssetDatabase.StartAssetEditing();
        try
        {
            EnsureFolder("Assets/Art/Prefabs");
            EnsureFolder("Assets/Art/Prefabs/Visuals");
            EnsureFolder(PrefabOutputDir);
            EnsureFolder("Assets/Art/Materials");
            EnsureFolder(ScreenshotDir);
        }
        finally
        {
            AssetDatabase.StopAssetEditing();
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
        }

        var fallbackMaterial = EnsureFallbackMaterial();
        var candidates = GetCandidates();
        var prefabInfo = new List<(Candidate candidate, string prefabPath, Vector3 visualScale, Vector3 visualRotation, bool hasRenderer, bool hasMaterial, bool usedFallback)>();

        foreach (var candidate in candidates)
        {
            var fbxPath = Path.Combine(FbxRoot, candidate.FbxName).Replace("\\", "/");
            var modelAsset = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
            if (modelAsset == null)
            {
                Debug.LogError("[Visual3B] Missing FBX: " + fbxPath);
                continue;
            }

            var root = new GameObject(candidate.PreviewName);
            var visual = (GameObject)PrefabUtility.InstantiatePrefab(modelAsset);
            if (visual == null)
            {
                UnityEngine.Object.DestroyImmediate(root);
                Debug.LogError("[Visual3B] Could not instantiate FBX: " + fbxPath);
                continue;
            }

            visual.name = "Visual";
            visual.transform.SetParent(root.transform, false);
            visual.transform.localPosition = Vector3.zero;
            visual.transform.localRotation = Quaternion.Euler(0f, candidate.Yaw, 0f);
            visual.transform.localScale = Vector3.one;

            RemoveGameplayAndCollisionComponents(root);
            var bounds = CalculateRendererBounds(root);
            if (bounds.size != Vector3.zero)
            {
                var height = Mathf.Max(0.001f, bounds.size.y);
                var footprint = Mathf.Max(bounds.size.x, bounds.size.z);
                var heightScale = TargetCharacterHeight / height;
                var footprintScale = footprint > 0.001f ? MaxFootprintSize / footprint : heightScale;
                var uniformScale = Mathf.Min(heightScale, footprintScale);
                visual.transform.localScale = Vector3.one * uniformScale;

                bounds = CalculateRendererBounds(root);
                root.transform.position -= new Vector3(0f, bounds.min.y, 0f);
            }

            var renderers = root.GetComponentsInChildren<Renderer>(true);
            var hasRenderer = renderers.Length > 0;
            var hasMaterial = false;
            var usedFallback = false;

            foreach (var renderer in renderers)
            {
                var mats = renderer.sharedMaterials;
                for (var i = 0; i < mats.Length; i++)
                {
                    var mat = mats[i];
                    var bad = mat == null || mat.shader == null || mat.shader.name.Contains("InternalErrorShader", StringComparison.OrdinalIgnoreCase);
                    if (bad)
                    {
                        mats[i] = fallbackMaterial;
                        usedFallback = true;
                    }
                    else
                    {
                        hasMaterial = true;
                    }
                }

                renderer.sharedMaterials = mats;
            }

            if (!hasMaterial && hasRenderer)
            {
                foreach (var renderer in renderers)
                {
                    var mats = renderer.sharedMaterials;
                    for (var i = 0; i < mats.Length; i++)
                    {
                        mats[i] = fallbackMaterial;
                    }

                    renderer.sharedMaterials = mats;
                }
                hasMaterial = true;
                usedFallback = true;
            }

            var prefabPath = Path.Combine(PrefabOutputDir, candidate.PreviewName + ".prefab").Replace("\\", "/");
            PrefabUtility.SaveAsPrefabAsset(root, prefabPath);

            prefabInfo.Add((candidate, prefabPath, visual.transform.localScale, visual.transform.localRotation.eulerAngles, hasRenderer, hasMaterial, usedFallback));
            UnityEngine.Object.DestroyImmediate(root);
        }

        var scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
        var lineupRoot = EnsureChild(null, "CharacterCandidatePreview");
        ClearChildren(lineupRoot);

        var groupRoots = new Dictionary<string, Transform>
        {
            { "Worker", EnsureChild(lineupRoot, "WorkerCandidates") },
            { "Light", EnsureChild(lineupRoot, "LightCandidates") },
            { "Heavy", EnsureChild(lineupRoot, "HeavyCandidates") },
            { "Ranged", EnsureChild(lineupRoot, "RangedCandidates") }
        };

        groupRoots["Worker"].localPosition = new Vector3(-8f, 0f, 4f);
        groupRoots["Light"].localPosition = new Vector3(-2f, 0f, 4f);
        groupRoots["Heavy"].localPosition = new Vector3(4f, 0f, 4f);
        groupRoots["Ranged"].localPosition = new Vector3(10f, 0f, 4f);

        var groupedPrefabs = prefabInfo.GroupBy(x => x.candidate.Group)
            .ToDictionary(g => g.Key, g => g.ToList());

        foreach (var kv in groupedPrefabs)
        {
            if (!groupRoots.TryGetValue(kv.Key, out var groupRoot))
            {
                continue;
            }

            for (var i = 0; i < kv.Value.Count; i++)
            {
                var data = kv.Value[i];
                var previewPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(data.prefabPath);
                if (previewPrefab == null)
                {
                    continue;
                }

                var instance = (GameObject)PrefabUtility.InstantiatePrefab(previewPrefab, scene);
                instance.name = data.candidate.PreviewName;
                instance.transform.SetParent(groupRoot, true);
                instance.transform.localPosition = new Vector3((i % 2) * 2.2f, 0f, -(i / 2) * 2.6f);
                instance.transform.localRotation = Quaternion.identity;
                instance.transform.localScale = Vector3.one;
            }
        }

        EnsureDirectionalLight(scene);
        var camera = EnsurePreviewCamera(scene);
        if (camera != null)
        {
            Capture(camera, Path.Combine(ScreenshotDir, "Visual_3B_CharacterPreview_AllCandidates.png").Replace("\\", "/"), new Vector3(2f, 14f, -6f), Quaternion.Euler(60f, 0f, 0f), 55f);
            Capture(camera, Path.Combine(ScreenshotDir, "Visual_3B_CharacterPreview_WorkerLight.png").Replace("\\", "/"), new Vector3(-5f, 8f, -4f), Quaternion.Euler(52f, 8f, 0f), 48f);
            Capture(camera, Path.Combine(ScreenshotDir, "Visual_3B_CharacterPreview_HeavyRanged.png").Replace("\\", "/"), new Vector3(7f, 8f, -4f), Quaternion.Euler(52f, -8f, 0f), 48f);
        }

        EditorSceneManager.MarkSceneDirty(scene);
        EditorSceneManager.SaveScene(scene);
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        var reportPath = "VISUAL_3B_CHARACTER_PREVIEW_AUTOGEN_SUMMARY.md";
        File.WriteAllText(reportPath, BuildSummary(prefabInfo), System.Text.Encoding.UTF8);
        Debug.Log("[Visual3B] Completed. Auto summary written to " + reportPath);
    }

    private static string BuildSummary(List<(Candidate candidate, string prefabPath, Vector3 visualScale, Vector3 visualRotation, bool hasRenderer, bool hasMaterial, bool usedFallback)> prefabInfo)
    {
        var lines = new List<string>
        {
            "# Visual 3B Auto Summary",
            "",
            "Generated: " + DateTime.UtcNow.ToString("u", CultureInfo.InvariantCulture),
            "",
            "| Group | FBX | Preview Prefab | Visual Scale | Visual Rotation | Renderer | Material | Fallback Material |",
            "|---|---|---|---|---|---|---|---|"
        };

        foreach (var row in prefabInfo.OrderBy(x => x.candidate.Group).ThenBy(x => x.candidate.PreviewName))
        {
            lines.Add(string.Format(CultureInfo.InvariantCulture,
                "| {0} | {1} | {2} | {3:F3},{4:F3},{5:F3} | {6:F1},{7:F1},{8:F1} | {9} | {10} | {11} |",
                row.candidate.Group,
                row.candidate.FbxName,
                row.prefabPath,
                row.visualScale.x, row.visualScale.y, row.visualScale.z,
                row.visualRotation.x, row.visualRotation.y, row.visualRotation.z,
                row.hasRenderer ? "Yes" : "No",
                row.hasMaterial ? "Yes" : "No",
                row.usedFallback ? "Yes" : "No"));
        }

        lines.Add("");
        lines.Add("Screenshots:");
        lines.Add("- Assets/Screenshots/Visual_3B_CharacterPreview_AllCandidates.png");
        lines.Add("- Assets/Screenshots/Visual_3B_CharacterPreview_WorkerLight.png");
        lines.Add("- Assets/Screenshots/Visual_3B_CharacterPreview_HeavyRanged.png");
        lines.Add("");

        return string.Join("\n", lines);
    }

    private static void RemoveGameplayAndCollisionComponents(GameObject root)
    {
        var components = root.GetComponentsInChildren<Component>(true);
        foreach (var component in components)
        {
            if (component == null)
            {
                continue;
            }

            if (component is Transform || component is Renderer || component is SkinnedMeshRenderer || component is MeshFilter || component is Animator)
            {
                continue;
            }

            if (component is Collider || component is Rigidbody || component is Joint)
            {
                UnityEngine.Object.DestroyImmediate(component);
                continue;
            }

            var type = component.GetType();
            if (type.Namespace != null && type.Namespace.StartsWith("UnityEngine", StringComparison.Ordinal))
            {
                continue;
            }

            UnityEngine.Object.DestroyImmediate(component);
        }
    }

    private static Bounds CalculateRendererBounds(GameObject root)
    {
        var renderers = root.GetComponentsInChildren<Renderer>(true);
        if (renderers.Length == 0)
        {
            return new Bounds(root.transform.position, Vector3.zero);
        }

        var combined = renderers[0].bounds;
        for (var i = 1; i < renderers.Length; i++)
        {
            combined.Encapsulate(renderers[i].bounds);
        }

        return combined;
    }

    private static void EnsureFolder(string path)
    {
        if (AssetDatabase.IsValidFolder(path))
        {
            return;
        }

        var parent = Path.GetDirectoryName(path)?.Replace("\\", "/");
        var leaf = Path.GetFileName(path);
        if (string.IsNullOrEmpty(parent) || string.IsNullOrEmpty(leaf))
        {
            return;
        }

        EnsureFolder(parent);
        AssetDatabase.CreateFolder(parent, leaf);
    }

    private static Material EnsureFallbackMaterial()
    {
        var existing = AssetDatabase.LoadAssetAtPath<Material>(MaterialOutputPath);
        if (existing != null)
        {
            return existing;
        }

        var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
        var material = new Material(shader)
        {
            color = new Color(0.72f, 0.78f, 0.88f, 1f)
        };

        AssetDatabase.CreateAsset(material, MaterialOutputPath);
        return material;
    }

    private static Transform EnsureChild(Transform parent, string name)
    {
        GameObject found = null;
        if (parent == null)
        {
            found = GameObject.Find(name);
        }
        else
        {
            var child = parent.Find(name);
            if (child != null)
            {
                found = child.gameObject;
            }
        }

        if (found == null)
        {
            found = new GameObject(name);
            if (parent != null)
            {
                found.transform.SetParent(parent, false);
            }
        }

        return found.transform;
    }

    private static void ClearChildren(Transform parent)
    {
        var children = new List<Transform>();
        foreach (Transform child in parent)
        {
            children.Add(child);
        }

        foreach (var child in children)
        {
            UnityEngine.Object.DestroyImmediate(child.gameObject);
        }
    }

    private static void EnsureDirectionalLight(UnityEngine.SceneManagement.Scene scene)
    {
        var lights = scene.GetRootGameObjects().SelectMany(x => x.GetComponentsInChildren<Light>(true)).ToArray();
        if (lights.Any(x => x.type == LightType.Directional))
        {
            return;
        }

        var go = new GameObject("VisualPreview_DirectionalLight");
        var light = go.AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = 1.1f;
        go.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
    }

    private static Camera EnsurePreviewCamera(UnityEngine.SceneManagement.Scene scene)
    {
        var camera = scene.GetRootGameObjects().SelectMany(x => x.GetComponentsInChildren<Camera>(true)).FirstOrDefault();
        if (camera != null)
        {
            return camera;
        }

        var cameraGo = new GameObject("VisualPreview_Camera");
        camera = cameraGo.AddComponent<Camera>();
        camera.clearFlags = CameraClearFlags.Skybox;
        camera.nearClipPlane = 0.01f;
        camera.farClipPlane = 200f;
        return camera;
    }

    private static void Capture(Camera camera, string assetPath, Vector3 position, Quaternion rotation, float fov)
    {
        camera.transform.position = position;
        camera.transform.rotation = rotation;
        camera.fieldOfView = fov;

        const int width = 1920;
        const int height = 1080;
        var rt = new RenderTexture(width, height, 24);
        var tex = new Texture2D(width, height, TextureFormat.RGB24, false);
        var previous = camera.targetTexture;
        var prevActive = RenderTexture.active;

        try
        {
            camera.targetTexture = rt;
            camera.Render();

            RenderTexture.active = rt;
            tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
            tex.Apply();

            var bytes = tex.EncodeToPNG();
            File.WriteAllBytes(assetPath, bytes);
        }
        finally
        {
            camera.targetTexture = previous;
            RenderTexture.active = prevActive;
            UnityEngine.Object.DestroyImmediate(rt);
            UnityEngine.Object.DestroyImmediate(tex);
        }
    }

    private static List<Candidate> GetCandidates()
    {
        return new List<Candidate>
        {
            new Candidate { Group = "Worker", FbxName = "Worker_Male.fbx", PreviewName = "Preview_Worker_Male", Yaw = 180f },
            new Candidate { Group = "Worker", FbxName = "Worker_Female.fbx", PreviewName = "Preview_Worker_Female", Yaw = 180f },
            new Candidate { Group = "Worker", FbxName = "Casual_Male.fbx", PreviewName = "Preview_Casual_Male", Yaw = 180f },
            new Candidate { Group = "Worker", FbxName = "Casual_Female.fbx", PreviewName = "Preview_Casual_Female", Yaw = 180f },

            new Candidate { Group = "Light", FbxName = "Soldier_Male.fbx", PreviewName = "Preview_Soldier_Male", Yaw = 180f },
            new Candidate { Group = "Light", FbxName = "Soldier_Female.fbx", PreviewName = "Preview_Soldier_Female", Yaw = 180f },
            new Candidate { Group = "Light", FbxName = "BlueSoldier_Male.fbx", PreviewName = "Preview_BlueSoldier_Male", Yaw = 180f },
            new Candidate { Group = "Light", FbxName = "Ninja_Male.fbx", PreviewName = "Preview_Ninja_Male", Yaw = 180f },

            new Candidate { Group = "Heavy", FbxName = "Knight_Male.fbx", PreviewName = "Preview_Knight_Male", Yaw = 180f },
            new Candidate { Group = "Heavy", FbxName = "Knight_Golden_Male.fbx", PreviewName = "Preview_Knight_Golden_Male", Yaw = 180f },
            new Candidate { Group = "Heavy", FbxName = "Viking_Male.fbx", PreviewName = "Preview_Viking_Male", Yaw = 180f },
            new Candidate { Group = "Heavy", FbxName = "Goblin_Male.fbx", PreviewName = "Preview_Goblin_Male", Yaw = 180f },

            new Candidate { Group = "Ranged", FbxName = "Wizard.fbx", PreviewName = "Preview_Wizard", Yaw = 180f },
            new Candidate { Group = "Ranged", FbxName = "Witch.fbx", PreviewName = "Preview_Witch", Yaw = 180f },
            new Candidate { Group = "Ranged", FbxName = "Elf.fbx", PreviewName = "Preview_Elf", Yaw = 180f }
        };
    }
}
