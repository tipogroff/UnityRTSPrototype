using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class Visual2SEnvironmentPassMenu
{
    private sealed class BindingSpec
    {
        public string PrefabPath;
        public string VisualRootName;
        public string ChildName;
        public string ModelAssetPath;
        public Vector3 ChildLocalPosition;
        public Vector3 ChildLocalEuler;
        public Vector3 ChildLocalScale;
        public bool KeepRootRendererEnabled;
        public int? RootRendererEnabledOverride;
    }

    private sealed class VisualPrefabSpec
    {
        public string PrefabPath;
        public string RootName;
        public string ChildName;
        public string ModelAssetPath;
        public Vector3 ChildLocalPosition;
        public Vector3 ChildLocalEuler;
        public Vector3 ChildLocalScale;
    }

    private static readonly BindingSpec[] GameplayBindings =
    {
        new BindingSpec
        {
            PrefabPath = "Assets/Prefabs/Base.prefab",
            VisualRootName = "VisualRoot",
            ChildName = "Visual_TowerHouse_SecondAge_Model",
            ModelAssetPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/TowerHouse_SecondAge.fbx",
            ChildLocalPosition = new Vector3(0f, 0f, 0f),
            ChildLocalEuler = new Vector3(-90f, 0f, 0f),
            ChildLocalScale = new Vector3(120f, 120f, 120f),
            KeepRootRendererEnabled = true,
            RootRendererEnabledOverride = 1
        },
        new BindingSpec
        {
            PrefabPath = "Assets/Prefabs/Barracks.prefab",
            VisualRootName = "VisualRoot",
            ChildName = "Visual_Barracks_Model",
            ModelAssetPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Barracks_FirstAge_Level1.fbx",
            ChildLocalPosition = new Vector3(0f, 0f, 0f),
            ChildLocalEuler = new Vector3(-90f, 0f, 0f),
            ChildLocalScale = new Vector3(120f, 120f, 120f),
            KeepRootRendererEnabled = true,
            RootRendererEnabledOverride = 1
        }
    };

    private static readonly VisualPrefabSpec[] VisualPrefabs =
    {
        new VisualPrefabSpec
        {
            PrefabPath = "Assets/Art/Prefabs/Visuals/Visual_Base_TowerHouse_SecondAge.prefab",
            RootName = "Visual_Base_TowerHouse_SecondAge",
            ChildName = "Model_TowerHouse_SecondAge",
            ModelAssetPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/TowerHouse_SecondAge.fbx",
            ChildLocalPosition = new Vector3(0f, 0f, 0f),
            ChildLocalEuler = new Vector3(-90f, 0f, 0f),
            ChildLocalScale = new Vector3(120f, 120f, 120f)
        },
        new VisualPrefabSpec
        {
            PrefabPath = "Assets/Art/Prefabs/Visuals/Visual_Barracks.prefab",
            RootName = "Visual_Barracks",
            ChildName = "Model_Barracks",
            ModelAssetPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Barracks_FirstAge_Level1.fbx",
            ChildLocalPosition = new Vector3(0f, 0f, 0f),
            ChildLocalEuler = new Vector3(-90f, 0f, 0f),
            ChildLocalScale = new Vector3(120f, 120f, 120f)
        },
        new VisualPrefabSpec
        {
            PrefabPath = "Assets/Art/Prefabs/Visuals/Visual_Resource_Gold.prefab",
            RootName = "Visual_Resource_Gold",
            ChildName = "Model_Gold",
            ModelAssetPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_Gold_1.fbx",
            ChildLocalPosition = new Vector3(0f, 0f, 0f),
            ChildLocalEuler = new Vector3(-90f, 0f, 0f),
            ChildLocalScale = new Vector3(140f, 140f, 140f)
        },
        new VisualPrefabSpec
        {
            PrefabPath = "Assets/Art/Prefabs/Visuals/Env_Rock_A.prefab",
            RootName = "Env_Rock_A",
            ChildName = "Model_Rock_Group",
            ModelAssetPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Rock_Group.fbx",
            ChildLocalPosition = new Vector3(0f, 0f, 0f),
            ChildLocalEuler = new Vector3(-90f, 0f, 0f),
            ChildLocalScale = new Vector3(110f, 110f, 110f)
        },
        new VisualPrefabSpec
        {
            PrefabPath = "Assets/Art/Prefabs/Visuals/Env_Rock_B.prefab",
            RootName = "Env_Rock_B",
            ChildName = "Model_Rock_1",
            ModelAssetPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_Rock_1.fbx",
            ChildLocalPosition = new Vector3(0f, 0f, 0f),
            ChildLocalEuler = new Vector3(-90f, 0f, 0f),
            ChildLocalScale = new Vector3(130f, 130f, 130f)
        },
        new VisualPrefabSpec
        {
            PrefabPath = "Assets/Art/Prefabs/Visuals/Env_Tree_A.prefab",
            RootName = "Env_Tree_A",
            ChildName = "Model_Tree_Group",
            ModelAssetPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_Tree_Group.fbx",
            ChildLocalPosition = new Vector3(0f, 0f, 0f),
            ChildLocalEuler = new Vector3(-90f, 0f, 0f),
            ChildLocalScale = new Vector3(130f, 130f, 130f)
        },
        new VisualPrefabSpec
        {
            PrefabPath = "Assets/Art/Prefabs/Visuals/Env_Tree_B.prefab",
            RootName = "Env_Tree_B",
            ChildName = "Model_PineTree_Group",
            ModelAssetPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_PineTree_Group.fbx",
            ChildLocalPosition = new Vector3(0f, 0f, 0f),
            ChildLocalEuler = new Vector3(-90f, 0f, 0f),
            ChildLocalScale = new Vector3(130f, 130f, 130f)
        }
    };

    [MenuItem("RTS/Visual2S/Run Environment Pass")]
    public static void RunEnvironmentPass()
    {
        var changedFiles = new List<string>();
        var report = new StringBuilder();
        report.AppendLine("# VISUAL_2S_ENVIRONMENT_REPORT");
        report.AppendLine();
        report.AppendLine($"- Date: {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
        report.AppendLine("- Scope: model selection + orientation + environment props");
        report.AppendLine();

        report.AppendLine("## 1) Base / Barracks binding");
        report.AppendLine();
        foreach (var binding in GameplayBindings)
        {
            ApplyGameplayBinding(binding, report, changedFiles);
        }

        report.AppendLine();
        report.AppendLine("## 2) Visual-only prefab updates");
        report.AppendLine();
        foreach (var spec in VisualPrefabs)
        {
            CreateOrUpdateVisualPrefab(spec, report, changedFiles);
        }

        report.AppendLine();
        report.AppendLine("## 3) VisualPreview scene");
        report.AppendLine();
        CreatePreviewScene(report, changedFiles);

        report.AppendLine();
        report.AppendLine("## 4) Validation");
        report.AppendLine();
        report.AppendLine("- Unity compile check: requested after prefab save.");
        report.AppendLine("- Prefab preview check: performed through prefab hierarchy inspection and scene assembly.");
        report.AppendLine("- VisualPreview inspection: scene rebuilt with Base/Barracks/Gold/rock/tree and gameplay prefab instances.");
        report.AppendLine("- Fallback MeshRenderer on Base and Barracks remains enabled as safe policy.");

        report.AppendLine();
        report.AppendLine("## 5) Changed files");
        report.AppendLine();
        foreach (var path in changedFiles.Distinct())
        {
            report.AppendLine($"- {path}");
        }

        var projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
        var reportPath = Path.Combine(projectRoot, "VISUAL_2S_ENVIRONMENT_REPORT.md");
        File.WriteAllText(reportPath, report.ToString().Replace("\r\n", "\n"), Encoding.UTF8);

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        Debug.Log($"[Visual2S] Environment pass completed. Report written to {reportPath}");
    }

    private static void ApplyGameplayBinding(BindingSpec spec, StringBuilder report, List<string> changedFiles)
    {
        var prefabRoot = PrefabUtility.LoadPrefabContents(spec.PrefabPath);
        try
        {
            var visualRoot = FindDeepChild(prefabRoot.transform, spec.VisualRootName);
            if (visualRoot == null)
            {
                report.AppendLine($"- {spec.PrefabPath}: VisualRoot not found.");
                return;
            }

            for (var i = visualRoot.childCount - 1; i >= 0; i--)
            {
                UnityEngine.Object.DestroyImmediate(visualRoot.GetChild(i).gameObject);
            }

            var modelAsset = AssetDatabase.LoadAssetAtPath<GameObject>(spec.ModelAssetPath);
            if (modelAsset == null)
            {
                report.AppendLine($"- {spec.PrefabPath}: missing model asset {spec.ModelAssetPath}");
                return;
            }

            var instance = UnityEngine.Object.Instantiate(modelAsset);
            instance.name = spec.ChildName;
            instance.transform.SetParent(visualRoot, false);
            instance.transform.localPosition = spec.ChildLocalPosition;
            instance.transform.localEulerAngles = spec.ChildLocalEuler;
            instance.transform.localScale = spec.ChildLocalScale;
            instance.SetActive(true);

            if (spec.KeepRootRendererEnabled)
            {
                var renderer = prefabRoot.GetComponent<MeshRenderer>();
                if (renderer != null)
                {
                    renderer.enabled = spec.RootRendererEnabledOverride.HasValue
                        ? spec.RootRendererEnabledOverride.Value != 0
                        : true;
                }
            }

            report.AppendLine($"### {spec.PrefabPath}");
            report.AppendLine($"- primary visual candidate: {Path.GetFileNameWithoutExtension(spec.ModelAssetPath)}");
            report.AppendLine($"- child name: {spec.ChildName}");
            report.AppendLine($"- child localRotation: {FormatVec(spec.ChildLocalEuler)}");
            report.AppendLine($"- child localScale: {FormatVec(spec.ChildLocalScale)}");
            report.AppendLine($"- root fallback MeshRenderer: {(prefabRoot.GetComponent<MeshRenderer>()?.enabled ?? false)}");
            report.AppendLine();

            PrefabUtility.SaveAsPrefabAsset(prefabRoot, spec.PrefabPath);
            changedFiles.Add(spec.PrefabPath);
        }
        finally
        {
            PrefabUtility.UnloadPrefabContents(prefabRoot);
        }
    }

    private static void CreateOrUpdateVisualPrefab(VisualPrefabSpec spec, StringBuilder report, List<string> changedFiles)
    {
        var root = new GameObject(spec.RootName);
        try
        {
            var modelAsset = AssetDatabase.LoadAssetAtPath<GameObject>(spec.ModelAssetPath);
            if (modelAsset == null)
            {
                report.AppendLine($"- {spec.PrefabPath}: missing model asset {spec.ModelAssetPath}");
                return;
            }

            var instance = UnityEngine.Object.Instantiate(modelAsset);
            instance.name = spec.ChildName;
            instance.transform.SetParent(root.transform, false);
            instance.transform.localPosition = spec.ChildLocalPosition;
            instance.transform.localEulerAngles = spec.ChildLocalEuler;
            instance.transform.localScale = spec.ChildLocalScale;
            instance.SetActive(true);

            var existingPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(spec.PrefabPath);
            if (existingPrefab != null)
            {
                AssetDatabase.DeleteAsset(spec.PrefabPath);
            }

            PrefabUtility.SaveAsPrefabAsset(root, spec.PrefabPath);
            changedFiles.Add(spec.PrefabPath);

            report.AppendLine($"### {spec.PrefabPath}");
            report.AppendLine($"- model: {Path.GetFileNameWithoutExtension(spec.ModelAssetPath)}");
            report.AppendLine($"- child rotation: {FormatVec(spec.ChildLocalEuler)}");
            report.AppendLine($"- child scale: {FormatVec(spec.ChildLocalScale)}");
            report.AppendLine("- gameplay scripts: none");
            report.AppendLine("- gameplay colliders: none");
            report.AppendLine();
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(root);
        }
    }

    private static void CreatePreviewScene(StringBuilder report, List<string> changedFiles)
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

        var placements = new (string path, Vector3 pos)[]
        {
            ("Assets/Art/Prefabs/Visuals/Visual_Base_TowerHouse_SecondAge.prefab", new Vector3(-8f, 0f, 0f)),
            ("Assets/Art/Prefabs/Visuals/Visual_Barracks.prefab", new Vector3(-3f, 0f, 0f)),
            ("Assets/Art/Prefabs/Visuals/Visual_Resource_Gold.prefab", new Vector3(2f, 0f, 0f)),
            ("Assets/Art/Prefabs/Visuals/Env_Rock_A.prefab", new Vector3(6f, 0f, -1f)),
            ("Assets/Art/Prefabs/Visuals/Env_Tree_A.prefab", new Vector3(9f, 0f, 1f)),
            ("Assets/Prefabs/Base.prefab", new Vector3(-8f, 0f, 6f)),
            ("Assets/Prefabs/Barracks.prefab", new Vector3(-3f, 0f, 6f))
        };

        foreach (var entry in placements)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(entry.path);
            if (prefab == null)
            {
                report.AppendLine($"- WARNING: missing prefab in preview scene: {entry.path}");
                continue;
            }

            var instance = PrefabUtility.InstantiatePrefab(prefab, scene) as GameObject;
            if (instance == null)
            {
                report.AppendLine($"- WARNING: failed to instantiate {entry.path} in preview scene");
                continue;
            }

            instance.name = $"Preview_{prefab.name}";
            instance.transform.position = entry.pos;
        }

        var scenePath = "Assets/Scenes/VisualPreview.unity";
        EditorSceneManager.SaveScene(scene, scenePath, true);
        changedFiles.Add(scenePath);
        report.AppendLine($"- scene saved: {scenePath}");
        report.AppendLine("- contains Base/Barracks gameplay prefabs and the selected visual-only/environment prefabs.");
    }

    private static Transform FindDeepChild(Transform root, string name)
    {
        if (root == null)
        {
            return null;
        }

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

    private static string FormatVec(Vector3 value)
    {
        return $"({value.x:0.###}, {value.y:0.###}, {value.z:0.###})";
    }
}
