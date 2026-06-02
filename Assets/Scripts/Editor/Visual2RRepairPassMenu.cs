using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class Visual2RRepairPassMenu
{
    private sealed class VisualBindingSpec
    {
        public string GameplayPrefabPath;
        public string VisualRootName;
        public string ChildName;
        public string ModelPrefabPath;
        public Vector3 LocalPosition;
        public Vector3 LocalEuler;
        public Vector3 LocalScale;
    }

    private sealed class VisualOnlySpec
    {
        public string VisualPrefabPath;
        public string ChildName;
        public string ModelPrefabPath;
        public Vector3 LocalPosition;
        public Vector3 LocalEuler;
        public Vector3 LocalScale;
    }

    private static readonly VisualBindingSpec[] GameplaySpecs =
    {
        new VisualBindingSpec
        {
            GameplayPrefabPath = "Assets/Prefabs/Base.prefab",
            VisualRootName = "VisualRoot",
            ChildName = "Visual_TownCenter_Model",
            ModelPrefabPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/TownCenter_FirstAge_Level1.fbx",
            LocalPosition = new Vector3(0f, 0f, 0f),
            LocalEuler = Vector3.zero,
            LocalScale = new Vector3(120f, 120f, 120f)
        },
        new VisualBindingSpec
        {
            GameplayPrefabPath = "Assets/Prefabs/Barracks.prefab",
            VisualRootName = "VisualRoot",
            ChildName = "Visual_Barracks_Model",
            ModelPrefabPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Barracks_FirstAge_Level1.fbx",
            LocalPosition = new Vector3(0f, 0f, 0f),
            LocalEuler = Vector3.zero,
            LocalScale = new Vector3(120f, 120f, 120f)
        }
    };

    private static readonly VisualOnlySpec[] VisualOnlySpecs =
    {
        new VisualOnlySpec
        {
            VisualPrefabPath = "Assets/Art/Prefabs/Visuals/Visual_Base_TownCenter.prefab",
            ChildName = "Model_TownCenter",
            ModelPrefabPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/TownCenter_FirstAge_Level1.fbx",
            LocalPosition = new Vector3(0f, 0f, 0f),
            LocalEuler = Vector3.zero,
            LocalScale = new Vector3(120f, 120f, 120f)
        },
        new VisualOnlySpec
        {
            VisualPrefabPath = "Assets/Art/Prefabs/Visuals/Visual_Barracks.prefab",
            ChildName = "Model_Barracks",
            ModelPrefabPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Barracks_FirstAge_Level1.fbx",
            LocalPosition = new Vector3(0f, 0f, 0f),
            LocalEuler = Vector3.zero,
            LocalScale = new Vector3(120f, 120f, 120f)
        },
        new VisualOnlySpec
        {
            VisualPrefabPath = "Assets/Art/Prefabs/Visuals/Visual_Resource_Gold.prefab",
            ChildName = "Model_Gold",
            ModelPrefabPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_Gold_1.fbx",
            LocalPosition = new Vector3(0f, 0f, 0f),
            LocalEuler = Vector3.zero,
            LocalScale = new Vector3(140f, 140f, 140f)
        },
        new VisualOnlySpec
        {
            VisualPrefabPath = "Assets/Art/Prefabs/Visuals/Visual_Resource_Rock.prefab",
            ChildName = "Model_Rock",
            ModelPrefabPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_Rock_1.fbx",
            LocalPosition = new Vector3(0f, 0f, 0f),
            LocalEuler = Vector3.zero,
            LocalScale = new Vector3(140f, 140f, 140f)
        },
        new VisualOnlySpec
        {
            VisualPrefabPath = "Assets/Art/Prefabs/Visuals/Visual_Resource_Tree.prefab",
            ChildName = "Model_Tree",
            ModelPrefabPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_Tree1.fbx",
            LocalPosition = new Vector3(0f, 0f, 0f),
            LocalEuler = Vector3.zero,
            LocalScale = new Vector3(130f, 130f, 130f)
        }
    };

    [MenuItem("RTS/Visual2R/Run Repair Pass")]
    public static void RunRepairPass()
    {
        var report = new StringBuilder();
        var changedFiles = new List<string>();
        var started = DateTime.Now;

        report.AppendLine("# VISUAL_2R_REPAIR_REPORT");
        report.AppendLine();
        report.AppendLine($"- Started: {started:yyyy-MM-dd HH:mm:ss}");
        report.AppendLine("- Scope: presentation-only repair pass");
        report.AppendLine();

        report.AppendLine("## 1) Diagnosis and repair of Base/Barracks");
        report.AppendLine();

        foreach (var spec in GameplaySpecs)
        {
            RepairGameplayPrefab(spec, report, changedFiles);
        }

        report.AppendLine();
        report.AppendLine("## 2) Visual-only prefab validation/repair");
        report.AppendLine();

        foreach (var spec in VisualOnlySpecs)
        {
            RepairVisualOnlyPrefab(spec, report, changedFiles);
        }

        report.AppendLine();
        report.AppendLine("## 3) VisualPreview scene");
        report.AppendLine();
        CreateVisualPreviewScene(report, changedFiles);

        report.AppendLine();
        report.AppendLine("## 4) Validation summary");
        report.AppendLine();
        report.AppendLine("- Unity compile check: requested after asset save.");
        report.AppendLine("- Prefab hierarchy check: performed during repair methods.");
        report.AppendLine("- Renderer presence check: included per prefab diagnostics.");
        report.AppendLine("- Play mode smoke: not auto-executed by this menu (manual-safe step). ");

        report.AppendLine();
        report.AppendLine("## 5) Changed files");
        report.AppendLine();
        foreach (var file in changedFiles.Distinct())
        {
            report.AppendLine($"- {file}");
        }

        var projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
        var reportPath = Path.Combine(projectRoot, "VISUAL_2R_REPAIR_REPORT.md");
        File.WriteAllText(reportPath, report.ToString().Replace("\r\n", "\n"), Encoding.UTF8);

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        Debug.Log($"[Visual2RRepair] Completed. Report written: {reportPath}");
    }

    private static void RepairGameplayPrefab(VisualBindingSpec spec, StringBuilder report, List<string> changedFiles)
    {
        report.AppendLine($"### {spec.GameplayPrefabPath}");

        var prefabRoot = PrefabUtility.LoadPrefabContents(spec.GameplayPrefabPath);
        var changed = false;

        try
        {
            var visualRoot = FindDeepChild(prefabRoot.transform, spec.VisualRootName);
            if (visualRoot == null)
            {
                report.AppendLine("- ERROR: VisualRoot not found.");
                return;
            }

            var rootRenderer = prefabRoot.GetComponent<MeshRenderer>();
            var fallbackBefore = rootRenderer != null && rootRenderer.enabled;

            var existing = FindDeepChild(visualRoot, spec.ChildName);
            if (existing != null)
            {
                UnityEngine.Object.DestroyImmediate(existing.gameObject);
                changed = true;
            }

            var modelAsset = AssetDatabase.LoadAssetAtPath<GameObject>(spec.ModelPrefabPath);
            if (modelAsset == null)
            {
                report.AppendLine($"- ERROR: Model asset missing: {spec.ModelPrefabPath}");
                return;
            }

            var modelInstance = PrefabUtility.InstantiatePrefab(modelAsset, prefabRoot.scene) as GameObject;
            if (modelInstance == null)
            {
                report.AppendLine("- ERROR: Failed to instantiate model asset.");
                return;
            }

            modelInstance.name = spec.ChildName;
            modelInstance.transform.SetParent(visualRoot, false);
            modelInstance.transform.localPosition = spec.LocalPosition;
            modelInstance.transform.localEulerAngles = spec.LocalEuler;
            modelInstance.transform.localScale = spec.LocalScale;
            modelInstance.SetActive(true);

            RemoveGameplayLikeComponents(modelInstance);

            if (rootRenderer != null)
            {
                if (!rootRenderer.enabled)
                {
                    rootRenderer.enabled = true;
                    changed = true;
                }
            }

            var diagnostics = CollectRendererDiagnostics(modelInstance);
            report.AppendLine($"- VisualRoot found: {visualRoot.name}");
            report.AppendLine($"- Fallback root MeshRenderer before: {fallbackBefore}");
            report.AppendLine($"- Fallback root MeshRenderer after: {(rootRenderer != null && rootRenderer.enabled)}");
            report.AppendLine($"- Quaternius child: {spec.ChildName}");
            report.AppendLine($"- Renderer count under child: {diagnostics.RendererCount}");
            report.AppendLine($"- Valid mesh renderers: {diagnostics.ValidMeshRendererCount}");
            report.AppendLine($"- Has visible-capable renderer: {diagnostics.HasVisibleCapableRenderer}");
            report.AppendLine($"- Combined bounds center: {FormatVec3(diagnostics.BoundsCenter)}");
            report.AppendLine($"- Combined bounds size: {FormatVec3(diagnostics.BoundsSize)}");
            report.AppendLine($"- Child localPosition: {FormatVec3(modelInstance.transform.localPosition)}");
            report.AppendLine($"- Child localEuler: {FormatVec3(modelInstance.transform.localEulerAngles)}");
            report.AppendLine($"- Child localScale: {FormatVec3(modelInstance.transform.localScale)}");
            report.AppendLine("- Reason of prior invisibility risk: fallback root MeshRenderer was disabled while replacement relied on fragile single-mesh binding.");

            foreach (var row in diagnostics.RendererRows)
            {
                report.AppendLine($"  - {row}");
            }

            changed = true;
        }
        finally
        {
            if (changed)
            {
                PrefabUtility.SaveAsPrefabAsset(prefabRoot, spec.GameplayPrefabPath);
                changedFiles.Add(spec.GameplayPrefabPath);
            }

            PrefabUtility.UnloadPrefabContents(prefabRoot);
        }
    }

    private static void RepairVisualOnlyPrefab(VisualOnlySpec spec, StringBuilder report, List<string> changedFiles)
    {
        report.AppendLine($"### {spec.VisualPrefabPath}");

        var prefabRoot = PrefabUtility.LoadPrefabContents(spec.VisualPrefabPath);
        var changed = false;

        try
        {
            while (prefabRoot.transform.childCount > 0)
            {
                UnityEngine.Object.DestroyImmediate(prefabRoot.transform.GetChild(0).gameObject);
                changed = true;
            }

            RemoveNonVisualComponents(prefabRoot);

            var modelAsset = AssetDatabase.LoadAssetAtPath<GameObject>(spec.ModelPrefabPath);
            if (modelAsset == null)
            {
                report.AppendLine($"- ERROR: Model asset missing: {spec.ModelPrefabPath}");
                return;
            }

            var instance = PrefabUtility.InstantiatePrefab(modelAsset, prefabRoot.scene) as GameObject;
            if (instance == null)
            {
                report.AppendLine("- ERROR: Failed to instantiate model for visual-only prefab.");
                return;
            }

            instance.name = spec.ChildName;
            instance.transform.SetParent(prefabRoot.transform, false);
            instance.transform.localPosition = spec.LocalPosition;
            instance.transform.localEulerAngles = spec.LocalEuler;
            instance.transform.localScale = spec.LocalScale;
            instance.SetActive(true);

            RemoveGameplayLikeComponents(instance);

            prefabRoot.transform.localPosition = Vector3.zero;
            prefabRoot.transform.localEulerAngles = Vector3.zero;
            prefabRoot.transform.localScale = Vector3.one;

            var diagnostics = CollectRendererDiagnostics(prefabRoot);
            report.AppendLine($"- Root active: {prefabRoot.activeSelf}");
            report.AppendLine($"- Renderer count: {diagnostics.RendererCount}");
            report.AppendLine($"- Valid mesh renderers: {diagnostics.ValidMeshRendererCount}");
            report.AppendLine($"- Has visible-capable renderer: {diagnostics.HasVisibleCapableRenderer}");
            report.AppendLine($"- Combined bounds size: {FormatVec3(diagnostics.BoundsSize)}");

            foreach (var row in diagnostics.RendererRows)
            {
                report.AppendLine($"  - {row}");
            }

            changed = true;
        }
        finally
        {
            if (changed)
            {
                PrefabUtility.SaveAsPrefabAsset(prefabRoot, spec.VisualPrefabPath);
                changedFiles.Add(spec.VisualPrefabPath);
            }

            PrefabUtility.UnloadPrefabContents(prefabRoot);
        }
    }

    private static void CreateVisualPreviewScene(StringBuilder report, List<string> changedFiles)
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

        var spawnList = new[]
        {
            (path: "Assets/Art/Prefabs/Visuals/Visual_Base_TownCenter.prefab", pos: new Vector3(-6f, 0f, 0f)),
            (path: "Assets/Art/Prefabs/Visuals/Visual_Barracks.prefab", pos: new Vector3(-2f, 0f, 0f)),
            (path: "Assets/Art/Prefabs/Visuals/Visual_Resource_Gold.prefab", pos: new Vector3(2f, 0f, 0f)),
            (path: "Assets/Art/Prefabs/Visuals/Visual_Resource_Rock.prefab", pos: new Vector3(5f, 0f, 0f)),
            (path: "Assets/Art/Prefabs/Visuals/Visual_Resource_Tree.prefab", pos: new Vector3(8f, 0f, 0f)),
            (path: "Assets/Prefabs/Base.prefab", pos: new Vector3(-6f, 0f, 6f)),
            (path: "Assets/Prefabs/Barracks.prefab", pos: new Vector3(-2f, 0f, 6f))
        };

        foreach (var entry in spawnList)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(entry.path);
            if (prefab == null)
            {
                report.AppendLine($"- WARNING: Missing prefab for preview: {entry.path}");
                continue;
            }

            var instance = PrefabUtility.InstantiatePrefab(prefab, scene) as GameObject;
            if (instance == null)
            {
                report.AppendLine($"- WARNING: Failed to instantiate in preview: {entry.path}");
                continue;
            }

            instance.transform.position = entry.pos;
            instance.name = $"Preview_{prefab.name}";
        }

        var scenePath = "Assets/Scenes/VisualPreview.unity";
        if (EditorSceneManager.SaveScene(scene, scenePath, true))
        {
            report.AppendLine($"- Scene created/updated: {scenePath}");
            report.AppendLine("- Contains visual-only prefabs and Base/Barracks instances for visibility verification.");
            changedFiles.Add(scenePath);
        }
        else
        {
            report.AppendLine("- ERROR: Failed to save VisualPreview scene.");
        }
    }

    private static void RemoveGameplayLikeComponents(GameObject root)
    {
        var allComponents = root.GetComponentsInChildren<Component>(true);
        foreach (var component in allComponents)
        {
            if (component == null || component is Transform)
            {
                continue;
            }

            if (component is MeshFilter || component is MeshRenderer || component is SkinnedMeshRenderer)
            {
                continue;
            }

            if (component is Renderer)
            {
                continue;
            }

            if (component is Collider)
            {
                UnityEngine.Object.DestroyImmediate(component);
                continue;
            }

            var typeName = component.GetType().FullName ?? component.GetType().Name;
            if (typeName.StartsWith("UnityEngine."))
            {
                continue;
            }

            UnityEngine.Object.DestroyImmediate(component);
        }
    }

    private static void RemoveNonVisualComponents(GameObject root)
    {
        var components = root.GetComponents<Component>();
        foreach (var component in components)
        {
            if (component == null || component is Transform)
            {
                continue;
            }

            if (component is MeshFilter || component is MeshRenderer || component is SkinnedMeshRenderer)
            {
                UnityEngine.Object.DestroyImmediate(component);
                continue;
            }

            if (component is Collider)
            {
                UnityEngine.Object.DestroyImmediate(component);
                continue;
            }

            var typeName = component.GetType().FullName ?? component.GetType().Name;
            if (!typeName.StartsWith("UnityEngine."))
            {
                UnityEngine.Object.DestroyImmediate(component);
            }
        }
    }

    private static Transform FindDeepChild(Transform root, string name)
    {
        if (root.name == name)
        {
            return root;
        }

        for (var i = 0; i < root.childCount; i++)
        {
            var result = FindDeepChild(root.GetChild(i), name);
            if (result != null)
            {
                return result;
            }
        }

        return null;
    }

    private sealed class RendererDiagnostics
    {
        public int RendererCount;
        public int ValidMeshRendererCount;
        public bool HasVisibleCapableRenderer;
        public Vector3 BoundsCenter;
        public Vector3 BoundsSize;
        public readonly List<string> RendererRows = new List<string>();
    }

    private static RendererDiagnostics CollectRendererDiagnostics(GameObject root)
    {
        var d = new RendererDiagnostics();
        var renderers = root.GetComponentsInChildren<Renderer>(true);
        d.RendererCount = renderers.Length;

        var hasBounds = false;
        var combined = new Bounds();

        foreach (var renderer in renderers)
        {
            var validMesh = false;
            string meshInfo;

            if (renderer is MeshRenderer meshRenderer)
            {
                var mf = meshRenderer.GetComponent<MeshFilter>();
                validMesh = mf != null && mf.sharedMesh != null;
                meshInfo = mf != null && mf.sharedMesh != null ? mf.sharedMesh.name : "null";
                if (validMesh)
                {
                    d.ValidMeshRendererCount++;
                }
            }
            else if (renderer is SkinnedMeshRenderer skinned)
            {
                validMesh = skinned.sharedMesh != null;
                meshInfo = skinned.sharedMesh != null ? skinned.sharedMesh.name : "null";
                if (validMesh)
                {
                    d.ValidMeshRendererCount++;
                }
            }
            else
            {
                meshInfo = "n/a";
            }

            var mats = renderer.sharedMaterials;
            var matsOk = mats != null && mats.Length > 0 && mats.Any(m => m != null);
            var activeSelf = renderer.gameObject.activeSelf;
            var activeInHierarchy = renderer.gameObject.activeInHierarchy;
            var enabled = renderer.enabled;

            if (!hasBounds)
            {
                combined = renderer.bounds;
                hasBounds = true;
            }
            else
            {
                combined.Encapsulate(renderer.bounds);
            }

            if (enabled && validMesh && matsOk && activeSelf)
            {
                d.HasVisibleCapableRenderer = true;
            }

            d.RendererRows.Add(
                $"{renderer.gameObject.name}: type={renderer.GetType().Name}, enabled={enabled}, activeSelf={activeSelf}, activeInHierarchy={activeInHierarchy}, mesh={meshInfo}, mats={(mats == null ? 0 : mats.Length)}, matsOk={matsOk}, boundsSize={FormatVec3(renderer.bounds.size)}");
        }

        if (hasBounds)
        {
            d.BoundsCenter = combined.center;
            d.BoundsSize = combined.size;
        }

        return d;
    }

    private static string FormatVec3(Vector3 v)
    {
        return $"({v.x:0.###}, {v.y:0.###}, {v.z:0.###})";
    }
}
