#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;

namespace RTS.Editor.Visual
{
    public static class Visual3EAAnimationRigInventory
    {
        private const string UltimatePackRoot = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack";
        private const string UalRoot = "Assets/Art/Quaternius/UniversalAnimationLibrary";

        private const string WorkerPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual_Male.fbx";
        private const string LightPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Viking_Male.fbx";
        private const string HeavyPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Knight_Male.fbx";
        private const string RangedPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Wizard.fbx";

        private const string JsonOutputPath = "Assets/Visual3EA_AnimationRigInventory.json";
        private const string MarkdownOutputFileName = "VISUAL_3E_A_ANIMATION_RIG_INVENTORY_REPORT.md";

        [Serializable]
        private sealed class InventoryRoot
        {
            public string generatedAtUtc;
            public string unityVersion;
            public string note;
            public FolderInventory[] folders;
            public SelectedCharacterInventory[] selectedCharacters;
            public UalInventory ual;
            public MappingCandidate[] mappingCandidates;
            public OptionRecommendation[] visual3ebOptions;
            public string recommendedOption;
            public string recommendedRationale;
            public string[] nonChangedGuardrails;
        }

        [Serializable]
        private sealed class FolderInventory
        {
            public string folderPath;
            public string[] fbxAssets;
            public string[] standaloneAnimationClipAssets;
            public string[] avatarAssets;
            public FbxInventory[] fbxImportDetails;
        }

        [Serializable]
        private sealed class FbxInventory
        {
            public string assetPath;
            public string animationType;
            public string avatarDefinition;
            public string importAnimation;
            public string clipCount;
            public ClipInventory[] clips;
            public string embeddedAvatarCount;
            public string humanoidAvatarCount;
            public string importWarnings;
        }

        [Serializable]
        private sealed class ClipInventory
        {
            public string name;
            public string loopTime;
            public string loopPose;
            public string cycleOffset;
        }

        [Serializable]
        private sealed class SelectedCharacterInventory
        {
            public string role;
            public string assetPath;
            public string hasSkinnedMeshRenderer;
            public string skinnedMeshRendererCount;
            public string hasSkeletonBones;
            public string totalBoneReferences;
            public string embeddedClipCount;
            public string[] embeddedClipNames;
            public string rigType;
            public string hasHumanoidAvatar;
            public string humanoidAvatarName;
            public string importWarnings;
            public string canRetargetUalHumanoidClips;
            public string retargetingReason;
        }

        [Serializable]
        private sealed class UalInventory
        {
            public string rootPath;
            public string primaryAssetPath;
            public string rigType;
            public string hasHumanoidAvatar;
            public string humanoidAvatarName;
            public string clipCount;
            public string[] clipNames;
            public string importWarnings;
            public string compatibilityWithSelectedCharacters;
        }

        [Serializable]
        private sealed class MappingCandidate
        {
            public string gameplayState;
            public string[] candidateClips;
            public string sourceAsset;
            public string confidence;
            public string notes;
        }

        [Serializable]
        private sealed class OptionRecommendation
        {
            public string option;
            public string summary;
            public string[] pros;
            public string[] risks;
            public string[] visual3ebImportChanges;
            public string[] visual3ebGameplayPrefabsTouched;
        }

        [MenuItem("RTS/Visual/Visual-3E-A Animation Rig Inventory")]
        public static void RunInventory()
        {
            var projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));

            var root = new InventoryRoot
            {
                generatedAtUtc = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture),
                unityVersion = Application.unityVersion,
                note = "Inventory/readiness pass only. No runtime wiring or gameplay prefab changes are made by this tool.",
                folders = new[]
                {
                    BuildFolderInventory(UltimatePackRoot),
                    BuildFolderInventory(UalRoot)
                }
            };

            var selected = new List<SelectedCharacterInventory>
            {
                BuildSelectedCharacter("Worker", WorkerPath),
                BuildSelectedCharacter("Light", LightPath),
                BuildSelectedCharacter("Heavy", HeavyPath),
                BuildSelectedCharacter("Ranged", RangedPath)
            };

            var ual = BuildUalInventory();
            root.selectedCharacters = selected.ToArray();
            root.ual = ual;
            root.mappingCandidates = BuildMappingCandidates(ual, root.folders);
            root.visual3ebOptions = BuildOptionRecommendations();
            root.recommendedOption = "Option C";
            root.recommendedRationale = "Current imports are Generic with no humanoid avatars, so pure humanoid retargeting is not ready; hybrid adoption minimizes import churn while enabling immediate Idle/Walk/Attack/Death coverage and a controlled Harvest fallback.";
            root.nonChangedGuardrails = BuildGuardrails();

            var json = JsonUtility.ToJson(root, true);
            var jsonAbsolutePath = Path.Combine(projectRoot, JsonOutputPath.Replace('/', Path.DirectorySeparatorChar));
            File.WriteAllText(jsonAbsolutePath, json);

            var markdown = BuildMarkdown(root);
            var markdownPath = Path.Combine(projectRoot, MarkdownOutputFileName);
            File.WriteAllText(markdownPath, markdown);

            AssetDatabase.Refresh();
            Debug.Log("[Visual3EA] Inventory complete: " + JsonOutputPath + " and " + MarkdownOutputFileName);
        }

        private static FolderInventory BuildFolderInventory(string folderPath)
        {
            var fbxGuids = AssetDatabase.FindAssets("t:Model", new[] { folderPath });
            var clipGuids = AssetDatabase.FindAssets("t:AnimationClip", new[] { folderPath });
            var avatarGuids = AssetDatabase.FindAssets("t:Avatar", new[] { folderPath });

            var fbxPaths = fbxGuids
                .Select(AssetDatabase.GUIDToAssetPath)
                .Where(IsFbx)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
                .ToArray();

            var standaloneClips = clipGuids
                .Select(AssetDatabase.GUIDToAssetPath)
                .Where(x => x.EndsWith(".anim", StringComparison.OrdinalIgnoreCase))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
                .ToArray();

            var avatarAssets = avatarGuids
                .Select(AssetDatabase.GUIDToAssetPath)
                .Where(path => !string.Equals(path, string.Empty, StringComparison.Ordinal))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
                .ToArray();

            var details = fbxPaths.Select(BuildFbxInventory).ToArray();

            return new FolderInventory
            {
                folderPath = folderPath,
                fbxAssets = fbxPaths,
                standaloneAnimationClipAssets = standaloneClips,
                avatarAssets = avatarAssets,
                fbxImportDetails = details
            };
        }

        private static FbxInventory BuildFbxInventory(string assetPath)
        {
            var importer = AssetImporter.GetAtPath(assetPath) as ModelImporter;
            if (importer == null)
            {
                return new FbxInventory
                {
                    assetPath = assetPath,
                    animationType = "unknown",
                    avatarDefinition = "unknown",
                    importAnimation = "unknown",
                    clipCount = "unknown",
                    clips = Array.Empty<ClipInventory>(),
                    embeddedAvatarCount = "unknown",
                    humanoidAvatarCount = "unknown",
                    importWarnings = "unknown"
                };
            }

            var clips = GetImporterClips(importer);
            var avatars = AssetDatabase.LoadAllAssetsAtPath(assetPath).OfType<Avatar>().ToArray();
            var humanoidCount = avatars.Count(a => a != null && a.isHuman).ToString(CultureInfo.InvariantCulture);

            return new FbxInventory
            {
                assetPath = assetPath,
                animationType = importer.animationType.ToString(),
                avatarDefinition = importer.avatarSetup.ToString(),
                importAnimation = importer.importAnimation.ToString(),
                clipCount = clips.Length.ToString(CultureInfo.InvariantCulture),
                clips = clips,
                embeddedAvatarCount = avatars.Length.ToString(CultureInfo.InvariantCulture),
                humanoidAvatarCount = humanoidCount,
                importWarnings = GetImporterWarnings(importer)
            };
        }

        private static SelectedCharacterInventory BuildSelectedCharacter(string role, string assetPath)
        {
            var fbx = BuildFbxInventory(assetPath);
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);

            if (model == null)
            {
                return new SelectedCharacterInventory
                {
                    role = role,
                    assetPath = assetPath,
                    hasSkinnedMeshRenderer = "unknown",
                    skinnedMeshRendererCount = "unknown",
                    hasSkeletonBones = "unknown",
                    totalBoneReferences = "unknown",
                    embeddedClipCount = fbx.clipCount,
                    embeddedClipNames = fbx.clips.Select(c => c.name).ToArray(),
                    rigType = fbx.animationType,
                    hasHumanoidAvatar = "unknown",
                    humanoidAvatarName = "unknown",
                    importWarnings = fbx.importWarnings,
                    canRetargetUalHumanoidClips = "unknown",
                    retargetingReason = "Model asset could not be loaded."
                };
            }

            var renderers = model.GetComponentsInChildren<SkinnedMeshRenderer>(true);
            var boneRefs = 0;
            var hasBones = false;
            for (var i = 0; i < renderers.Length; i++)
            {
                var bones = renderers[i] != null ? renderers[i].bones : null;
                if (bones == null)
                {
                    continue;
                }

                boneRefs += bones.Count(b => b != null);
                if (!hasBones && boneRefs > 0)
                {
                    hasBones = true;
                }
            }

            var avatars = AssetDatabase.LoadAllAssetsAtPath(assetPath).OfType<Avatar>().Where(a => a != null).ToArray();
            var humanoidAvatar = avatars.FirstOrDefault(a => a.isHuman && a.isValid);

            var ual = BuildUalInventory();
            var rigIsHumanoid = string.Equals(fbx.animationType, ModelImporterAnimationType.Human.ToString(), StringComparison.OrdinalIgnoreCase);
            var ualHumanoid = string.Equals(ual.rigType, ModelImporterAnimationType.Human.ToString(), StringComparison.OrdinalIgnoreCase) &&
                              string.Equals(ual.hasHumanoidAvatar, "yes", StringComparison.OrdinalIgnoreCase);

            var canRetarget = rigIsHumanoid && humanoidAvatar != null && ualHumanoid;
            var reason = canRetarget
                ? "All required humanoid signals detected (character rig + humanoid avatar + UAL humanoid source)."
                : "One or more humanoid prerequisites missing; inspect rig/avatar settings before retargeting.";

            return new SelectedCharacterInventory
            {
                role = role,
                assetPath = assetPath,
                hasSkinnedMeshRenderer = renderers.Length > 0 ? "yes" : "no",
                skinnedMeshRendererCount = renderers.Length.ToString(CultureInfo.InvariantCulture),
                hasSkeletonBones = hasBones ? "yes" : "no",
                totalBoneReferences = boneRefs.ToString(CultureInfo.InvariantCulture),
                embeddedClipCount = fbx.clipCount,
                embeddedClipNames = fbx.clips.Select(c => c.name).ToArray(),
                rigType = fbx.animationType,
                hasHumanoidAvatar = humanoidAvatar != null ? "yes" : "no",
                humanoidAvatarName = humanoidAvatar != null ? humanoidAvatar.name : "unknown",
                importWarnings = fbx.importWarnings,
                canRetargetUalHumanoidClips = canRetarget ? "yes" : "no",
                retargetingReason = reason
            };
        }

        private static UalInventory BuildUalInventory()
        {
            var fbxPaths = AssetDatabase.FindAssets("t:Model", new[] { UalRoot })
                .Select(AssetDatabase.GUIDToAssetPath)
                .Where(IsFbx)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
                .ToArray();

            var primary = fbxPaths.FirstOrDefault(path => path.IndexOf("UAL", StringComparison.OrdinalIgnoreCase) >= 0)
                          ?? fbxPaths.FirstOrDefault();

            if (string.IsNullOrEmpty(primary))
            {
                return new UalInventory
                {
                    rootPath = UalRoot,
                    primaryAssetPath = "unknown",
                    rigType = "unknown",
                    hasHumanoidAvatar = "unknown",
                    humanoidAvatarName = "unknown",
                    clipCount = "0",
                    clipNames = Array.Empty<string>(),
                    importWarnings = "unknown",
                    compatibilityWithSelectedCharacters = "unknown"
                };
            }

            var fbx = BuildFbxInventory(primary);
            var avatars = AssetDatabase.LoadAllAssetsAtPath(primary).OfType<Avatar>().Where(a => a != null).ToArray();
            var humanoid = avatars.FirstOrDefault(a => a.isHuman && a.isValid);

            return new UalInventory
            {
                rootPath = UalRoot,
                primaryAssetPath = primary,
                rigType = fbx.animationType,
                hasHumanoidAvatar = humanoid != null ? "yes" : "no",
                humanoidAvatarName = humanoid != null ? humanoid.name : "unknown",
                clipCount = fbx.clipCount,
                clipNames = fbx.clips.Select(c => c.name).ToArray(),
                importWarnings = fbx.importWarnings,
                compatibilityWithSelectedCharacters = "Humanoid retargeting is expected only when both source and target import as humanoid with valid avatars."
            };
        }

        private static MappingCandidate[] BuildMappingCandidates(UalInventory ual, FolderInventory[] folders)
        {
            var ualClips = ual.clipNames ?? Array.Empty<string>();

            var ultimateFolder = folders.FirstOrDefault(f => string.Equals(f.folderPath, UltimatePackRoot, StringComparison.OrdinalIgnoreCase));
            var characterPackClips = (ultimateFolder?.fbxImportDetails ?? Array.Empty<FbxInventory>())
                .SelectMany(f => f.clips ?? Array.Empty<ClipInventory>())
                .Select(c => c.name)
                .Where(name => !string.IsNullOrWhiteSpace(name))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();

            return new[]
            {
                BuildStateMapping("Idle", ualClips, characterPackClips, new [] { "idle", "breath" }),
                BuildStateMapping("Walk", ualClips, characterPackClips, new [] { "walk", "run", "jog" }),
                BuildStateMapping("Attack", ualClips, characterPackClips, new [] { "attack", "slash", "hit", "shoot", "cast" }),
                BuildStateMapping("Harvest", ualClips, characterPackClips, new [] { "harvest", "gather", "mine", "chop", "work" }),
                BuildStateMapping("Death", ualClips, characterPackClips, new [] { "death", "die", "dead", "fall" })
            };
        }

        private static MappingCandidate BuildStateMapping(string state, string[] ualClips, string[] characterPackClips, string[] keywords)
        {
            var ualCandidates = FilterByKeywords(ualClips, keywords).Select(name => "UAL:" + name).ToList();
            var packCandidates = FilterByKeywords(characterPackClips, keywords).Select(name => "CharacterPack:" + name).ToList();

            var merged = ualCandidates.Concat(packCandidates)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Take(8)
                .ToArray();

            if (merged.Length == 0 && string.Equals(state, "Harvest", StringComparison.OrdinalIgnoreCase))
            {
                return new MappingCandidate
                {
                    gameplayState = state,
                    candidateClips = Array.Empty<string>(),
                    sourceAsset = "none detected",
                    confidence = "low",
                    notes = "No explicit harvest clip keyword detected. Fallback candidate for Visual-3E-B: reuse melee/work-like clip or procedural/VFX visual placeholder."
                };
            }

            var source = merged.Any(c => c.StartsWith("UAL:", StringComparison.Ordinal))
                ? (merged.Any(c => c.StartsWith("CharacterPack:", StringComparison.Ordinal)) ? "UAL + CharacterPack" : "UAL")
                : "CharacterPack";

            var confidence = merged.Length >= 3 ? "high" : (merged.Length >= 1 ? "medium" : "low");

            return new MappingCandidate
            {
                gameplayState = state,
                candidateClips = merged,
                sourceAsset = source,
                confidence = confidence,
                notes = merged.Length > 0 ? "Keyword-based candidate list; verify exact semantics in Visual-3E-B preview pass." : "No keyword match found."
            };
        }

        private static string[] FilterByKeywords(IEnumerable<string> clips, IEnumerable<string> keywords)
        {
            var keyList = keywords.Where(k => !string.IsNullOrWhiteSpace(k)).ToArray();
            return clips
                .Where(c => !string.IsNullOrWhiteSpace(c) && keyList.Any(k => c.IndexOf(k, StringComparison.OrdinalIgnoreCase) >= 0))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(c => c, StringComparer.OrdinalIgnoreCase)
                .ToArray();
        }

        private static OptionRecommendation[] BuildOptionRecommendations()
        {
            return new[]
            {
                new OptionRecommendation
                {
                    option = "Option A",
                    summary = "Use embedded clips from Ultimate Animated Character Pack.",
                    pros = new[]
                    {
                        "Asset locality per character can simplify authoring.",
                        "Potential style consistency between mesh and source clip set."
                    },
                    risks = new[]
                    {
                        "Clip coverage may vary per FBX and produce uneven gameplay-state mapping.",
                        "Cross-character timing/style drift can increase blend tuning effort."
                    },
                    visual3ebImportChanges = new[]
                    {
                        "Verify Import Animation is enabled for selected character FBX files.",
                        "Standardize loop settings for locomotion clips where needed.",
                        "Confirm consistent rig type across selected role models."
                    },
                    visual3ebGameplayPrefabsTouched = new[]
                    {
                        "Worker.prefab",
                        "Light.prefab",
                        "Heavy.prefab",
                        "Ranged.prefab"
                    }
                },
                new OptionRecommendation
                {
                    option = "Option B",
                    summary = "Use Universal Animation Library clips through humanoid retargeting.",
                    pros = new[]
                    {
                        "Centralized clip library may improve consistency and maintenance.",
                        "Easier to extend with additional states from one source."
                    },
                    risks = new[]
                    {
                        "Requires strict humanoid avatar compatibility on all target models.",
                        "Retargeting artifacts may require per-character pose/mask adjustments."
                    },
                    visual3ebImportChanges = new[]
                    {
                        "Ensure selected characters and UAL source import as Humanoid with valid avatars.",
                        "Set Avatar Definition strategy (Create From This Model / Copy From Other Avatar) consistently.",
                        "Tune loop settings and root transform options for locomotion/action clips."
                    },
                    visual3ebGameplayPrefabsTouched = new[]
                    {
                        "Worker.prefab",
                        "Light.prefab",
                        "Heavy.prefab",
                        "Ranged.prefab"
                    }
                },
                new OptionRecommendation
                {
                    option = "Option C",
                    summary = "Hybrid approach: Idle/Walk from UAL, Attack/Death from character pack, Harvest fallback procedural or work-like clip.",
                    pros = new[]
                    {
                        "Balances broad coverage with role-specific attacks/deaths.",
                        "Allows staged integration when harvest-specific clips are missing."
                    },
                    risks = new[]
                    {
                        "Mixed sources can create style mismatch between states.",
                        "Controller graph complexity increases due to heterogeneous clip provenance."
                    },
                    visual3ebImportChanges = new[]
                    {
                        "Keep UAL and selected characters humanoid-compatible for shared locomotion.",
                        "Normalize attack/death clip loop and transition timing from character pack.",
                        "Define temporary harvest fallback policy before full bespoke gather animations."
                    },
                    visual3ebGameplayPrefabsTouched = new[]
                    {
                        "Worker.prefab",
                        "Light.prefab",
                        "Heavy.prefab",
                        "Ranged.prefab"
                    }
                }
            };
        }

        private static string[] BuildGuardrails()
        {
            return new[]
            {
                "MatchManager not modified.",
                "ActionApplier not modified.",
                "ActionDecoder not modified.",
                "ActionMaskBuilder not modified.",
                "ObservationBuilder not modified.",
                "GridManager occupancy logic not modified.",
                "UnitFactory spawn semantics not modified.",
                "UnitRegistry registration semantics not modified.",
                "ResourceManager and ResourceNode gameplay semantics not modified.",
                "ML-Agents and Python training scripts not modified.",
                "Checkpoint paths and inference bridge not modified.",
                "Map coordinates and logical map size 24x24 not modified.",
                "Gameplay prefabs and UnitDef/GameConfig assets not modified.",
                "VisualEventBridge/UnitVisualAnimator/UnitFactory runtime wiring not modified in this stage."
            };
        }

        private static ClipInventory[] GetImporterClips(ModelImporter importer)
        {
            var source = importer.clipAnimations;
            if (source == null || source.Length == 0)
            {
                source = importer.defaultClipAnimations;
            }

            if (source == null || source.Length == 0)
            {
                return Array.Empty<ClipInventory>();
            }

            return source
                .Select(c => new ClipInventory
                {
                    name = string.IsNullOrWhiteSpace(c.name) ? "unknown" : c.name,
                    loopTime = c.loopTime.ToString(),
                    loopPose = c.loopPose.ToString(),
                    cycleOffset = c.cycleOffset.ToString(CultureInfo.InvariantCulture)
                })
                .ToArray();
        }

        private static string GetImporterWarnings(ModelImporter importer)
        {
            try
            {
                var prop = typeof(ModelImporter).GetProperty("importWarnings", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (prop == null)
                {
                    return "unknown";
                }

                var value = prop.GetValue(importer) as string;
                return string.IsNullOrWhiteSpace(value) ? "none" : value;
            }
            catch
            {
                return "unknown";
            }
        }

        private static bool IsFbx(string path)
        {
            return path.EndsWith(".fbx", StringComparison.OrdinalIgnoreCase);
        }

        private static string BuildMarkdown(InventoryRoot root)
        {
            var lines = new List<string>
            {
                "# VISUAL_3E_A_ANIMATION_RIG_INVENTORY_REPORT",
                string.Empty,
                "Generated (UTC): " + root.generatedAtUtc,
                "Unity: " + root.unityVersion,
                string.Empty,
                "## Scope",
                "- Stage: Visual-3E-A (inventory/readiness only)",
                "- Runtime animation wiring changes: none",
                "- Gameplay prefab edits: none",
                string.Empty,
                "## Checked Asset Folders",
                "- " + UltimatePackRoot,
                "- " + UalRoot,
                string.Empty
            };

            foreach (var folder in root.folders ?? Array.Empty<FolderInventory>())
            {
                lines.Add("### Folder: " + folder.folderPath);
                lines.Add("- FBX assets: " + (folder.fbxAssets?.Length ?? 0).ToString(CultureInfo.InvariantCulture));
                lines.Add("- Standalone AnimationClip assets (.anim): " + (folder.standaloneAnimationClipAssets?.Length ?? 0).ToString(CultureInfo.InvariantCulture));
                lines.Add("- Avatar assets: " + (folder.avatarAssets?.Length ?? 0).ToString(CultureInfo.InvariantCulture));

                var rigGroup = (folder.fbxImportDetails ?? Array.Empty<FbxInventory>())
                    .GroupBy(f => string.IsNullOrWhiteSpace(f.animationType) ? "unknown" : f.animationType)
                    .OrderBy(g => g.Key, StringComparer.OrdinalIgnoreCase)
                    .Select(g => g.Key + "=" + g.Count().ToString(CultureInfo.InvariantCulture));

                lines.Add("- FBX rig type distribution: " + (rigGroup.Any() ? string.Join(", ", rigGroup) : "unknown"));
                lines.Add(string.Empty);
            }

            lines.Add("## Selected Character Model Validation");
            lines.Add("| Role | Asset | SkinnedMeshRenderer | Bones | Embedded Clips | Rig Type | Humanoid Avatar | Retarget UAL | Import Warnings |");
            lines.Add("|---|---|---|---|---|---|---|---|---|");

            foreach (var c in root.selectedCharacters ?? Array.Empty<SelectedCharacterInventory>())
            {
                lines.Add(string.Format(CultureInfo.InvariantCulture,
                    "| {0} | {1} | {2} ({3}) | {4} ({5}) | {6} | {7} | {8} ({9}) | {10} | {11} |",
                    c.role,
                    c.assetPath,
                    c.hasSkinnedMeshRenderer,
                    c.skinnedMeshRendererCount,
                    c.hasSkeletonBones,
                    c.totalBoneReferences,
                    c.embeddedClipCount,
                    c.rigType,
                    c.hasHumanoidAvatar,
                    c.humanoidAvatarName,
                    c.canRetargetUalHumanoidClips,
                    c.importWarnings));
            }

            lines.Add(string.Empty);
            lines.Add("## Universal Animation Library Inventory");
            lines.Add("- Primary asset: " + root.ual.primaryAssetPath);
            lines.Add("- Rig type: " + root.ual.rigType);
            lines.Add("- Humanoid avatar: " + root.ual.hasHumanoidAvatar + " (" + root.ual.humanoidAvatarName + ")");
            lines.Add("- Clip count: " + root.ual.clipCount);
            lines.Add("- Import warnings: " + root.ual.importWarnings);
            lines.Add("- Compatibility note: " + root.ual.compatibilityWithSelectedCharacters);
            lines.Add(string.Empty);
            lines.Add("### UAL Clip Names");
            foreach (var clip in root.ual.clipNames ?? Array.Empty<string>())
            {
                lines.Add("- " + clip);
            }

            lines.Add(string.Empty);
            lines.Add("## Candidate Mapping (Idle/Walk/Attack/Harvest/Death)");
            lines.Add("| Gameplay state | Candidate clips | Source asset | Confidence |");
            lines.Add("|---|---|---|---|");

            foreach (var m in root.mappingCandidates ?? Array.Empty<MappingCandidate>())
            {
                var joined = (m.candidateClips == null || m.candidateClips.Length == 0)
                    ? "(none)"
                    : string.Join("; ", m.candidateClips);
                lines.Add("| " + m.gameplayState + " | " + joined + " | " + m.sourceAsset + " | " + m.confidence + " |");
                lines.Add("- Notes (" + m.gameplayState + "): " + m.notes);
            }

            lines.Add(string.Empty);
            lines.Add("## Visual-3E-B Options");
            foreach (var option in root.visual3ebOptions ?? Array.Empty<OptionRecommendation>())
            {
                lines.Add("### " + option.option + ": " + option.summary);
                lines.Add("- Pros:");
                foreach (var p in option.pros ?? Array.Empty<string>())
                {
                    lines.Add("  - " + p);
                }

                lines.Add("- Risks:");
                foreach (var r in option.risks ?? Array.Empty<string>())
                {
                    lines.Add("  - " + r);
                }

                lines.Add("- Import settings to review in Visual-3E-B:");
                foreach (var i in option.visual3ebImportChanges ?? Array.Empty<string>())
                {
                    lines.Add("  - " + i);
                }

                lines.Add("- Gameplay prefabs expected to be touched in Visual-3E-B:");
                foreach (var pref in option.visual3ebGameplayPrefabsTouched ?? Array.Empty<string>())
                {
                    lines.Add("  - " + pref);
                }
            }

            lines.Add(string.Empty);
            lines.Add("## Recommended Path For Visual-3E-B");
            lines.Add("- Recommended option: " + root.recommendedOption);
            lines.Add("- Rationale: " + root.recommendedRationale);

            lines.Add(string.Empty);
            lines.Add("## Non-changed Guardrails");
            foreach (var guardrail in root.nonChangedGuardrails ?? Array.Empty<string>())
            {
                lines.Add("- " + guardrail);
            }

            lines.Add(string.Empty);
            lines.Add("## Changed Files");
            lines.Add("- Assets/Editor/Visual3EAAnimationRigInventory.cs");
            lines.Add("- Assets/Visual3EA_AnimationRigInventory.json");
            lines.Add("- VISUAL_3E_A_ANIMATION_RIG_INVENTORY_REPORT.md");

            return string.Join("\n", lines);
        }
    }
}
#endif
