using System.Collections.Generic;
using RTS.Gameplay;
using RTS.MLAgents.Stage7B;
using RTS.MLAgents.Stage7B.TeacherReplay;
using RTS.Presentation;
using RTS.Presentation.CameraControls;
using RTS.Presentation.Selection;
using RTS.Presentation.UI;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace RTS.Editor.Presentation
{
        [System.Obsolete("Deprecated: final HumanPlay scene configuration is now serialized in Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity; do not use this editor setup for release scenes.")]
public static class HumanPlay3UiCameraMenuSetup
    {
        private const string MenuScenePath = "Assets/Scenes/MainMenu.unity";
        private const string DemoScenePath = "Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity";
        private const string HudPrefabPath = "Assets/Prefabs/UI/HumanPlayCanvas.prefab";
        private const string RpgPath = "Assets/Art/UI/Kenney/UI_Pack_RPG_Expansion";
        private const string IconsPath = "Assets/Art/UI/Kenney/Game_Icons";

                public static void Run()
        {
            AssetDatabase.StartAssetEditing();
            try
            {
                ConfigureSprites(RpgPath);
                ConfigureSprites(IconsPath);
            }
            finally
            {
                AssetDatabase.StopAssetEditing();
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            CreateHudPrefab();
            CreateMainMenuScene();
            ConfigureDemoScene();
            EnsureBuildSettings();
            AssetDatabase.SaveAssets();
            Debug.Log("[HumanPlay3UiCameraMenuSetup] Complete.");
        }

                public static void OpenMainMenu()
        {
            EditorSceneManager.OpenScene(MenuScenePath, OpenSceneMode.Single);
        }

                public static void OpenDemoScene()
        {
            EditorSceneManager.OpenScene(DemoScenePath, OpenSceneMode.Single);
        }

        private static void ConfigureSprites(string root)
        {
            string[] textureGuids = AssetDatabase.FindAssets("t:Texture2D", new[] { root });
            foreach (string guid in textureGuids)
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                TextureImporter importer = AssetImporter.GetAtPath(path) as TextureImporter;
                if (importer == null)
                {
                    continue;
                }

                importer.textureType = TextureImporterType.Sprite;
                importer.spriteImportMode = SpriteImportMode.Single;
                importer.spritePixelsPerUnit = 100f;
                importer.mipmapEnabled = false;
                importer.alphaIsTransparency = true;

                string file = System.IO.Path.GetFileNameWithoutExtension(path).ToLowerInvariant();
                if (file.Contains("panel"))
                {
                    importer.spriteBorder = new Vector4(18f, 18f, 18f, 18f);
                }
                else if (file.Contains("buttonlong") || file.Contains("buttonsquare"))
                {
                    importer.spriteBorder = new Vector4(12f, 12f, 12f, 12f);
                }

                importer.SaveAndReimport();
            }
        }

        private static void CreateHudPrefab()
        {
            GameObject root = new GameObject("HumanPlayCanvas", typeof(RectTransform), typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster), typeof(HumanPlayCanvasController));
            HumanPlayCanvasController controller = root.GetComponent<HumanPlayCanvasController>();
            AssignCommonSprites(controller);
            PrefabUtility.SaveAsPrefabAsset(root, HudPrefabPath);
            Object.DestroyImmediate(root);
        }

        private static void CreateMainMenuScene()
        {
            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            GameObject camera = new GameObject("Main Camera", typeof(Camera), typeof(AudioListener));
            camera.tag = "MainCamera";
            camera.transform.position = new Vector3(0f, 0f, -10f);

            GameObject light = new GameObject("Directional Light", typeof(Light));
            light.GetComponent<Light>().type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

            GameObject controllers = new GameObject("MenuControllers", typeof(SceneFlowController), typeof(MainMenuController));
            SceneFlowController flow = controllers.GetComponent<SceneFlowController>();
            SetString(flow, "_mainMenuSceneName", "MainMenu");
            SetString(flow, "_demoSceneName", "HumanPlay_Demo_PlayerVsAI");
            MainMenuController menu = controllers.GetComponent<MainMenuController>();
            SetObject(menu, "_sceneFlowController", flow);
            AssignMainMenuSprites(menu);

            EditorSceneManager.SaveScene(scene, MenuScenePath);
        }

        private static void ConfigureDemoScene()
        {
            Scene scene = EditorSceneManager.OpenScene(DemoScenePath, OpenSceneMode.Single);

            SceneFlowController flow = Object.FindFirstObjectByType<SceneFlowController>();
            if (flow == null)
            {
                flow = new GameObject("SceneFlowController", typeof(SceneFlowController)).GetComponent<SceneFlowController>();
            }

            SetString(flow, "_mainMenuSceneName", "MainMenu");
            SetString(flow, "_demoSceneName", "HumanPlay_Demo_PlayerVsAI");

            HumanPlayCanvasController canvas = Object.FindFirstObjectByType<HumanPlayCanvasController>(FindObjectsInactive.Include);
            if (canvas == null)
            {
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(HudPrefabPath);
                GameObject instance = prefab != null
                    ? (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene)
                    : new GameObject("HumanPlayCanvas", typeof(RectTransform), typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster), typeof(HumanPlayCanvasController));
                canvas = instance.GetComponent<HumanPlayCanvasController>();
            }

            AssignCommonSprites(canvas);
            DisableOldDiagnostics();
            ConfigureStartupFlow();
            ConfigureHumanMode();
            ConfigureSelectionUx();
            ConfigureCamera();

            EditorSceneManager.SaveScene(scene);
        }

        private static void DisableOldDiagnostics()
        {
            foreach (HumanPlayHudController hud in Object.FindObjectsByType<HumanPlayHudController>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                hud.enabled = false;
            }

            foreach (GameSpeedController speed in Object.FindObjectsByType<GameSpeedController>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                SetBool(speed, "_showOverlay", false);
            }
        }

        private static void ConfigureStartupFlow()
        {
            MlAgentsTrainingBootstrap bootstrap = Object.FindFirstObjectByType<MlAgentsTrainingBootstrap>(FindObjectsInactive.Include);
            if (bootstrap != null)
            {
                SetBool(bootstrap, "_autoStartEpisodeOnStart", false);
                SetBool(bootstrap, "_stepScriptedOpponent", false);
            }

            EpisodeController episode = Object.FindFirstObjectByType<EpisodeController>(FindObjectsInactive.Include);
            if (episode != null)
            {
                SetBool(episode, "_autoStartOnPlay", false);
            }

            Stage7BTeacherReplayDemoOrchestrator orchestrator =
                Object.FindFirstObjectByType<Stage7BTeacherReplayDemoOrchestrator>(FindObjectsInactive.Include);
            if (orchestrator != null)
            {
                orchestrator.enabled = false;
            }
        }

        private static void ConfigureHumanMode()
        {
            HumanPlayModeController mode = Object.FindFirstObjectByType<HumanPlayModeController>(FindObjectsInactive.Include);
            if (mode == null)
            {
                return;
            }

            SerializedObject so = new SerializedObject(mode);
            SetEnum(so, "_initialMode", "AIvsPlayer2");
            SetBool(so, "_autoStartOnEnable", true);
            SetFloat(so, "_autoStartRuntimeReadyTimeoutSeconds", 5f);
            SetBool(so, "_loadMenuSceneOnReturn", true);
            SetString(so, "_menuSceneName", "MainMenu");
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void ConfigureCamera()
        {
            Camera camera = Camera.main != null ? Camera.main : Object.FindFirstObjectByType<Camera>(FindObjectsInactive.Include);
            if (camera == null)
            {
                GameObject go = new GameObject("Main Camera", typeof(Camera), typeof(AudioListener));
                go.tag = "MainCamera";
                camera = go.GetComponent<Camera>();
            }

            camera.orthographic = true;
            camera.orthographicSize = 12f;
            camera.nearClipPlane = 0.1f;
            camera.farClipPlane = 500f;
            camera.transform.rotation = Quaternion.Euler(58f, 45f, 0f);
            camera.transform.position = new Vector3(11.5f, 18f, -9f);

            if (camera.GetComponent<RtsCameraController>() == null)
            {
                camera.gameObject.AddComponent<RtsCameraController>();
            }
        }

        private static void ConfigureSelectionUx()
        {
            PlayerSelectionController selectionController =
                Object.FindFirstObjectByType<PlayerSelectionController>(FindObjectsInactive.Include);
            if (selectionController == null)
            {
                GameObject presentationControls = GameObject.Find("PresentationControls");
                if (presentationControls == null)
                {
                    presentationControls = new GameObject("PresentationControls");
                }

                selectionController = presentationControls.AddComponent<PlayerSelectionController>();
            }

            SelectionManager selectionManager = selectionController.GetComponent<SelectionManager>();
            if (selectionManager == null)
            {
                selectionManager = selectionController.gameObject.AddComponent<SelectionManager>();
            }

            if (selectionController.GetComponent<SelectionMarkerController>() == null)
            {
                selectionController.gameObject.AddComponent<SelectionMarkerController>();
            }

            SetObject(selectionController, "_selectionManager", selectionManager);
        }

        private static void EnsureBuildSettings()
        {
            List<EditorBuildSettingsScene> existing = new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
            List<EditorBuildSettingsScene> ordered = new List<EditorBuildSettingsScene>
            {
                new EditorBuildSettingsScene(MenuScenePath, true),
                new EditorBuildSettingsScene(DemoScenePath, true)
            };

            for (int i = 0; i < existing.Count; i++)
            {
                EditorBuildSettingsScene scene = existing[i];
                if (scene.path == MenuScenePath || scene.path == DemoScenePath)
                {
                    continue;
                }

                ordered.Add(scene);
            }

            EditorBuildSettings.scenes = ordered.ToArray();
        }

        private static void AssignCommonSprites(Object target)
        {
            SetObject(target, "_panelSprite", LoadSprite(RpgPath + "/PNG/panel_brown.png"));
            SetObject(target, "_buttonSprite", LoadSprite(RpgPath + "/PNG/buttonLong_beige.png"));
            SetObject(target, "_buttonPressedSprite", LoadSprite(RpgPath + "/PNG/buttonLong_beige_pressed.png"));
            SetObject(target, "_pauseIcon", LoadSprite(IconsPath + "/PNG/White/2x/pause.png"));
            SetObject(target, "_gearIcon", LoadSprite(IconsPath + "/PNG/White/2x/gear.png"));
            SetObject(target, "_homeIcon", LoadSprite(IconsPath + "/PNG/White/2x/home.png"));
            SetObject(target, "_targetIcon", LoadSprite(IconsPath + "/PNG/White/2x/target.png"));
        }

        private static void AssignMainMenuSprites(Object target)
        {
            SetObject(target, "_panelSprite", LoadSprite(RpgPath + "/PNG/panel_brown.png"));
            SetObject(target, "_buttonSprite", LoadSprite(RpgPath + "/PNG/buttonLong_beige.png"));
            SetObject(target, "_buttonPressedSprite", LoadSprite(RpgPath + "/PNG/buttonLong_beige_pressed.png"));
            SetObject(target, "_settingsIcon", LoadSprite(IconsPath + "/PNG/White/2x/gear.png"));
            SetObject(target, "_quitIcon", LoadSprite(IconsPath + "/PNG/White/2x/power.png"));
        }

        private static Sprite LoadSprite(string path)
        {
            return AssetDatabase.LoadAssetAtPath<Sprite>(path);
        }

        private static void SetObject(Object target, string propertyName, Object value)
        {
            SerializedObject so = new SerializedObject(target);
            SerializedProperty property = so.FindProperty(propertyName);
            if (property != null)
            {
                property.objectReferenceValue = value;
                so.ApplyModifiedPropertiesWithoutUndo();
            }
        }

        private static void SetString(Object target, string propertyName, string value)
        {
            SerializedObject so = new SerializedObject(target);
            SetString(so, propertyName, value);
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void SetBool(Object target, string propertyName, bool value)
        {
            SerializedObject so = new SerializedObject(target);
            SetBool(so, propertyName, value);
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void SetString(SerializedObject so, string propertyName, string value)
        {
            SerializedProperty property = so.FindProperty(propertyName);
            if (property != null)
            {
                property.stringValue = value;
            }
        }

        private static void SetBool(SerializedObject so, string propertyName, bool value)
        {
            SerializedProperty property = so.FindProperty(propertyName);
            if (property != null)
            {
                property.boolValue = value;
            }
        }

        private static void SetFloat(SerializedObject so, string propertyName, float value)
        {
            SerializedProperty property = so.FindProperty(propertyName);
            if (property != null)
            {
                property.floatValue = value;
            }
        }

        private static void SetEnum(SerializedObject so, string propertyName, string enumName)
        {
            SerializedProperty property = so.FindProperty(propertyName);
            if (property == null || property.propertyType != SerializedPropertyType.Enum)
            {
                return;
            }

            for (int i = 0; i < property.enumNames.Length; i++)
            {
                if (property.enumNames[i] == enumName)
                {
                    property.enumValueIndex = i;
                    return;
                }
            }
        }
    }
}
