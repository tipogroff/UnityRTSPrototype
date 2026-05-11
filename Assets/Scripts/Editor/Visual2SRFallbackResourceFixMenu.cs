using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class Visual2SRFallbackResourceFixMenu
{
    private const string BasePrefabPath = "Assets/Prefabs/Base.prefab";
    private const string BarracksPrefabPath = "Assets/Prefabs/Barracks.prefab";
    private const string ResourcePrefabPath = "Assets/Prefabs/Resource.prefab";

    private const string VisualBasePrefabPath = "Assets/Art/Prefabs/Visuals/Visual_Base_TowerHouse_SecondAge.prefab";
    private const string VisualBarracksPrefabPath = "Assets/Art/Prefabs/Visuals/Visual_Barracks.prefab";
    private const string VisualGoldPrefabPath = "Assets/Art/Prefabs/Visuals/Visual_Resource_Gold.prefab";
    private const string VisualPreviewScenePath = "Assets/Scenes/VisualPreview.unity";

    private const string ResourceGoldModelPath = "Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_Gold_1.fbx";

    private sealed class FallbackSpec
    {
        public string PrefabPath;
        public string VisualRootName;
        public string ExpectedVisualChildName;
    }

    private sealed class RendererDiagnostic
    {
        public bool HasRenderer;
        public bool HasValidVisibleRenderer;
        public bool HasActiveVisualChild;
        public bool HasNonZeroScale;
        public bool ChildExists;
        public bool AllChecksPass;
        public string Reason;
        public Vector3 LocalPosition;
        public Vector3 LocalEuler;
        public Vector3 LocalScale;
        public List<string> Rows = new List<string>();
    }

    private static readonly FallbackSpec[] FallbackSpecs =
    {
        new FallbackSpec
        {
            PrefabPath = BasePrefabPath,
            VisualRootName = "VisualRoot",
            ExpectedVisualChildName = "Visual_TowerHouse_SecondAge_Model"
        },
        new FallbackSpec
        {
            PrefabPath = BarracksPrefabPath,
            VisualRootName = "VisualRoot",
            ExpectedVisualChildName = "Visual_Barracks_Model"
        }
    };

    [MenuItem("RTS/Visual2S-R/Run Fallback and Resource Binding Fix")]
    public static void RunFallbackAndResourceFix()
    {
        var changedFiles = new List<string>();
        var report = new StringBuilder();

        report.AppendLine("# VISUAL_2S_R_FALLBACK_RESOURCE_FIX_REPORT");
        report.AppendLine();
        report.AppendLine($"- Date: {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
        report.AppendLine("- Scope: fallback overlay removal + Resource_Gold_1 binding");
        report.AppendLine("- Safety mode: presentation-only");
        report.AppendLine();

        report.AppendLine("## 1) Base/Barracks fallback checks and actions");
        report.AppendLine();
        foreach (var spec in FallbackSpecs)
        {
            ProcessFallbackPrefab(spec, report, changedFiles);
        }

        report.AppendLine();
        report.AppendLine("## 2) Resource binding fix");
        report.AppendLine();
        ProcessResourcePrefab(report, changedFiles);

        report.AppendLine();
        report.AppendLine("## 3) VisualPreview refresh");
        report.AppendLine();
        UpdateVisualPreviewScene(report, changedFiles);

        report.AppendLine();
        report.AppendLine("## 4) Gameplay modules explicitly not changed");
        report.AppendLine();
        report.AppendLine("- MatchManager");
        report.AppendLine("- ActionApplier");
        report.AppendLine("- ActionDecoder");
        report.AppendLine("- ActionMaskBuilder");
        report.AppendLine("- ObservationBuilder");
        report.AppendLine("- GridManager occupancy logic");
        report.AppendLine("- UnitFactory spawn semantics");
        report.AppendLine("- UnitRegistry registration semantics");
        report.AppendLine("- ResourceManager / ResourceNode gameplay semantics");
        report.AppendLine("- ML-Agents training code and Python training scripts");
        report.AppendLine("- Checkpoint paths, inference bridge, runtime command semantics");

        report.AppendLine();
        report.AppendLine("## 5) Validation notes");
        report.AppendLine();
        report.AppendLine("- Root gameplay scripts/components were preserved on touched gameplay prefabs.");
        report.AppendLine("- Root gameplay colliders were not edited.");
        report.AppendLine("- Root transforms on gameplay prefabs were not edited.");
        report.AppendLine("- Visual transforms changed only on visual child objects.");
        report.AppendLine("- Working gameplay scene binding should be visually confirmed manually if not opened by this pass.");

        report.AppendLine();
        report.AppendLine("## 6) Changed files");
        report.AppendLine();
        foreach (var file in changedFiles.Distinct())
        {
            report.AppendLine($"- {file}");
        }

        var projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
        var reportPath = Path.Combine(projectRoot, "VISUAL_2S_R_FALLBACK_RESOURCE_FIX_REPORT.md");
        File.WriteAllText(reportPath, report.ToString().Replace("\r\n", "\n"), Encoding.UTF8);

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        Debug.Log($"[Visual2S-R] Pass completed. Report written to {reportPath}");
    }

    private static void ProcessFallbackPrefab(FallbackSpec spec, StringBuilder report, List<string> changedFiles)
    {
        report.AppendLine($"### {spec.PrefabPath}");

        var prefabRoot = PrefabUtility.LoadPrefabContents(spec.PrefabPath);
        var changed = false;

        try
        {
            var visualRoot = FindDeepChild(prefabRoot.transform, spec.VisualRootName);
            if (visualRoot == null)
            {
                report.AppendLine("- status: FAIL");
                report.AppendLine($"- reason: VisualRoot '{spec.VisualRootName}' not found.");
                return;
            }

            var visualChild = FindDeepChild(visualRoot, spec.ExpectedVisualChildName);
            var diag = EvaluateVisualChild(visualChild);

            report.AppendLine($"- visual child expected: {spec.ExpectedVisualChildName}");
            report.AppendLine($"- visual child found: {diag.ChildExists}");
            report.AppendLine($"- activeSelf == true: {diag.HasActiveVisualChild}");
            report.AppendLine($"- localScale non-zero: {diag.HasNonZeroScale}");
            report.AppendLine($"- has renderer(s): {diag.HasRenderer}");
            report.AppendLine($"- has valid visible renderer: {diag.HasValidVisibleRenderer}");

            if (diag.ChildExists)
            {
                report.AppendLine($"- visual localPosition: {FormatVec(diag.LocalPosition)}");
                report.AppendLine($"- visual localRotation: {FormatVec(diag.LocalEuler)}");
                report.AppendLine($"- visual localScale: {FormatVec(diag.LocalScale)}");
            }

            foreach (var row in diag.Rows)
            {
                report.AppendLine($"  - {row}");
            }

            var rootRenderer = prefabRoot.GetComponent<MeshRenderer>();
            if (rootRenderer == null)
            {
                report.AppendLine("- root fallback MeshRenderer: not found");
                report.AppendLine("- fallback action: none");
                return;
            }

            report.AppendLine($"- root fallback before: {rootRenderer.enabled}");

            if (diag.AllChecksPass)
            {
                if (rootRenderer.enabled)
                {
                    rootRenderer.enabled = false;
                    changed = true;
                }

                report.AppendLine($"- status: PASS");
                report.AppendLine($"- fallback action: disabled (MeshRenderer.enabled=false)");
            }
            else
            {
                report.AppendLine("- status: FAIL");
                report.AppendLine($"- reason: {diag.Reason}");
                report.AppendLine("- fallback action: kept unchanged");
            }

            report.AppendLine($"- root fallback after: {rootRenderer.enabled}");
        }
        finally
        {
            if (changed)
            {
                PrefabUtility.SaveAsPrefabAsset(prefabRoot, spec.PrefabPath);
                changedFiles.Add(spec.PrefabPath);
            }

            PrefabUtility.UnloadPrefabContents(prefabRoot);
        }
    }

    private static void ProcessResourcePrefab(StringBuilder report, List<string> changedFiles)
    {
        report.AppendLine($"### {ResourcePrefabPath}");

        var prefabRoot = PrefabUtility.LoadPrefabContents(ResourcePrefabPath);
        var changed = false;

        try
        {
            var rootComponents = prefabRoot.GetComponents<Component>()
                .Where(c => c != null)
                .Select(c => c.GetType().Name)
                .ToArray();
            report.AppendLine($"- root components before: {string.Join(", ", rootComponents)}");

            var visualRoot = FindDeepChild(prefabRoot.transform, "VisualRoot");
            if (visualRoot == null)
            {
                var go = new GameObject("VisualRoot");
                visualRoot = go.transform;
                visualRoot.SetParent(prefabRoot.transform, false);
                visualRoot.localPosition = Vector3.zero;
                visualRoot.localEulerAngles = Vector3.zero;
                visualRoot.localScale = Vector3.one;
                changed = true;
                report.AppendLine("- VisualRoot: created");
            }
            else
            {
                report.AppendLine("- VisualRoot: already exists");
            }

            var existingTargetChild = FindDeepChild(visualRoot, "Visual_Resource_Gold_Model");
            if (existingTargetChild != null)
            {
                UnityEngine.Object.DestroyImmediate(existingTargetChild.gameObject);
                changed = true;
            }

            var modelAsset = AssetDatabase.LoadAssetAtPath<GameObject>(ResourceGoldModelPath);
            if (modelAsset == null)
            {
                report.AppendLine($"- status: FAIL");
                report.AppendLine($"- reason: missing model asset {ResourceGoldModelPath}");
                return;
            }

            var modelInstance = UnityEngine.Object.Instantiate(modelAsset);
            modelInstance.name = "Visual_Resource_Gold_Model";
            modelInstance.transform.SetParent(visualRoot, false);
            modelInstance.transform.localPosition = Vector3.zero;
            modelInstance.transform.localEulerAngles = new Vector3(-90f, 0f, 0f);
            modelInstance.transform.localScale = new Vector3(140f, 140f, 140f);
            modelInstance.SetActive(true);
            changed = true;

            var diag = EvaluateVisualChild(modelInstance.transform);
            report.AppendLine($"- visual child: {modelInstance.name}");
            report.AppendLine($"- visual activeSelf == true: {diag.HasActiveVisualChild}");
            report.AppendLine($"- visual localScale non-zero: {diag.HasNonZeroScale}");
            report.AppendLine($"- visual has renderer(s): {diag.HasRenderer}");
            report.AppendLine($"- visual has valid visible renderer: {diag.HasValidVisibleRenderer}");
            report.AppendLine($"- visual localPosition: {FormatVec(modelInstance.transform.localPosition)}");
            report.AppendLine($"- visual localRotation: {FormatVec(modelInstance.transform.localEulerAngles)}");
            report.AppendLine($"- visual localScale: {FormatVec(modelInstance.transform.localScale)}");

            foreach (var row in diag.Rows)
            {
                report.AppendLine($"  - {row}");
            }

            var fallbackRenderer = prefabRoot.GetComponent<MeshRenderer>();
            if (fallbackRenderer != null)
            {
                report.AppendLine($"- green cube fallback before: {fallbackRenderer.enabled}");

                if (diag.AllChecksPass)
                {
                    if (fallbackRenderer.enabled)
                    {
                        fallbackRenderer.enabled = false;
                        changed = true;
                    }

                    report.AppendLine("- status: PASS");
                    report.AppendLine("- green cube fallback action: disabled (MeshRenderer.enabled=false)");
                }
                else
                {
                    report.AppendLine("- status: FAIL");
                    report.AppendLine($"- reason: {diag.Reason}");
                    report.AppendLine("- green cube fallback action: kept enabled");
                }

                report.AppendLine($"- green cube fallback after: {fallbackRenderer.enabled}");
            }
            else
            {
                report.AppendLine("- root MeshRenderer: not found (no green cube fallback present)");
            }
        }
        finally
        {
            if (changed)
            {
                PrefabUtility.SaveAsPrefabAsset(prefabRoot, ResourcePrefabPath);
                changedFiles.Add(ResourcePrefabPath);
            }

            PrefabUtility.UnloadPrefabContents(prefabRoot);
        }
    }

    private static void UpdateVisualPreviewScene(StringBuilder report, List<string> changedFiles)
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

        var placements = new (string path, Vector3 pos)[]
        {
            (VisualBasePrefabPath, new Vector3(-8f, 0f, 0f)),
            (VisualBarracksPrefabPath, new Vector3(-3f, 0f, 0f)),
            (VisualGoldPrefabPath, new Vector3(2f, 0f, 0f)),
            (BasePrefabPath, new Vector3(-8f, 0f, 6f)),
            (BarracksPrefabPath, new Vector3(-3f, 0f, 6f)),
            (ResourcePrefabPath, new Vector3(2f, 0f, 6f))
        };

        foreach (var placement in placements)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(placement.path);
            if (prefab == null)
            {
                report.AppendLine($"- WARNING: missing prefab for preview: {placement.path}");
                continue;
            }

            var instance = PrefabUtility.InstantiatePrefab(prefab, scene) as GameObject;
            if (instance == null)
            {
                report.AppendLine($"- WARNING: failed to instantiate prefab in preview: {placement.path}");
                continue;
            }

            instance.name = $"Preview_{prefab.name}";
            instance.transform.position = placement.pos;
        }

        EditorSceneManager.SaveScene(scene, VisualPreviewScenePath, true);
        changedFiles.Add(VisualPreviewScenePath);

        report.AppendLine($"- scene saved: {VisualPreviewScenePath}");
        report.AppendLine("- scene content includes Base/Barracks/Resource gameplay prefabs + Visual_Resource_Gold visual-only prefab.");
    }

    private static RendererDiagnostic EvaluateVisualChild(Transform visualChild)
    {
        var diag = new RendererDiagnostic
        {
            ChildExists = visualChild != null
        };

        if (visualChild == null)
        {
            diag.Reason = "visual child not found";
            return diag;
        }

        diag.LocalPosition = visualChild.localPosition;
        diag.LocalEuler = visualChild.localEulerAngles;
        diag.LocalScale = visualChild.localScale;

        diag.HasActiveVisualChild = visualChild.gameObject.activeSelf;
        var scale = visualChild.localScale;
        diag.HasNonZeroScale = Mathf.Abs(scale.x) > 0.0001f && Mathf.Abs(scale.y) > 0.0001f && Mathf.Abs(scale.z) > 0.0001f;

        var renderers = visualChild.GetComponentsInChildren<Renderer>(true);
        diag.HasRenderer = renderers.Length > 0;

        var hasValidVisibleRenderer = false;
        foreach (var renderer in renderers)
        {
            var rendererEnabled = renderer.enabled;
            var rendererActive = renderer.gameObject.activeInHierarchy;
            var hasMesh = false;
            var hasMaterial = false;

            if (renderer is MeshRenderer meshRenderer)
            {
                var meshFilter = meshRenderer.GetComponent<MeshFilter>();
                hasMesh = meshFilter != null && meshFilter.sharedMesh != null;
                hasMaterial = meshRenderer.sharedMaterials != null && meshRenderer.sharedMaterials.Any(m => m != null);
            }
            else if (renderer is SkinnedMeshRenderer skinnedMesh)
            {
                hasMesh = skinnedMesh.sharedMesh != null;
                hasMaterial = skinnedMesh.sharedMaterials != null && skinnedMesh.sharedMaterials.Any(m => m != null);
            }
            else
            {
                hasMaterial = renderer.sharedMaterials != null && renderer.sharedMaterials.Any(m => m != null);
            }

            diag.Rows.Add($"{renderer.name}: type={renderer.GetType().Name}, enabled={rendererEnabled}, activeInHierarchy={rendererActive}, mesh={hasMesh}, material={hasMaterial}");

            if (rendererEnabled && rendererActive && hasMesh && hasMaterial)
            {
                hasValidVisibleRenderer = true;
            }
        }

        diag.HasValidVisibleRenderer = hasValidVisibleRenderer;
        diag.AllChecksPass = diag.ChildExists && diag.HasActiveVisualChild && diag.HasNonZeroScale && diag.HasRenderer && diag.HasValidVisibleRenderer;

        if (!diag.AllChecksPass)
        {
            var reasons = new List<string>();
            if (!diag.ChildExists)
            {
                reasons.Add("visual child missing");
            }

            if (!diag.HasActiveVisualChild)
            {
                reasons.Add("visual child inactive");
            }

            if (!diag.HasNonZeroScale)
            {
                reasons.Add("visual child scale is zero");
            }

            if (!diag.HasRenderer)
            {
                reasons.Add("no renderers found");
            }

            if (!diag.HasValidVisibleRenderer)
            {
                reasons.Add("no renderer with enabled+mesh+material");
            }

            diag.Reason = string.Join("; ", reasons);
        }

        return diag;
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
            var child = FindDeepChild(root.GetChild(i), name);
            if (child != null)
            {
                return child;
            }
        }

        return null;
    }

    private static string FormatVec(Vector3 value)
    {
        return $"({value.x:0.###}, {value.y:0.###}, {value.z:0.###})";
    }
}