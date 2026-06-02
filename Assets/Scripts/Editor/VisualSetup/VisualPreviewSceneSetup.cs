using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.Editor.VisualSetup
{
    /// <summary>
    /// Editor utility to set up the VisualPreview scene with ground textures and game objects.
    /// Visual-2T Ground Texture Pass support script.
    /// </summary>
    public static class VisualPreviewSceneSetup
    {
        private const string VisualPreviewScenePath = "Assets/Scenes/VisualPreview.unity";
        private const string GroundMaterialPath = "Assets/Art/Materials/Ground_Stylized_Grass.mat";
        private const string BaseGUID = "0382cf14f5eac744b894d94eb4a9dc67"; // Base.prefab GUID
        private const string BarracksGUID = "7f4a2c8e1b3d5f9e02a6b4c8d0e2f1a3"; // Barracks.prefab GUID
        private const string ResourceGUID = "0061aee5f741cd843b33428afd4ecd6d"; // Resource.prefab GUID

        [MenuItem("RTS/Visual-2T/Setup VisualPreview Scene", priority = 1)]
        public static void SetupVisualPreview()
        {
            // Open the VisualPreview scene
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
                return;

            var scene = EditorSceneManager.OpenScene(VisualPreviewScenePath, OpenSceneMode.Single);

            // Create ground plane
            GameObject groundPlane = new GameObject("Ground_Stylized");
            groundPlane.transform.position = Vector3.zero;
            groundPlane.transform.localScale = new Vector3(24f, 1f, 24f);

            MeshFilter meshFilter = groundPlane.AddComponent<MeshFilter>();
            meshFilter.mesh = Resources.GetBuiltinResource<Mesh>("Cube.fbx");

            MeshRenderer meshRenderer = groundPlane.AddComponent<MeshRenderer>();
            Material groundMaterial = AssetDatabase.LoadAssetAtPath<Material>(GroundMaterialPath);
            if (groundMaterial != null)
                meshRenderer.material = groundMaterial;
            else
                Debug.LogWarning($"Could not load ground material at {GroundMaterialPath}");

            // Add box collider for gameplay (set to trigger so units can pass)
            BoxCollider collider = groundPlane.AddComponent<BoxCollider>();
            collider.isTrigger = true;

            EditorGUIUtility.PingObject(groundPlane);
            Debug.Log("✓ Ground plane created: Ground_Stylized");

            // Add Base at position (12, 0, 12)
            AddPrefabInstance("Base", new Vector3(12f, 0.5f, 12f), BaseGUID);
            
            // Add Barracks at offset
            AddPrefabInstance("Barracks_Preview", new Vector3(14f, 0.5f, 12f), BarracksGUID);
            
            // Add Resource at offset
            AddPrefabInstance("Resource_Gold_1_Preview", new Vector3(16f, 0.5f, 12f), ResourceGUID);

            EditorSceneManager.SaveScene(scene);
            Debug.Log("✓ VisualPreview scene setup complete!");
            Debug.Log("  - Ground material applied");
            Debug.Log("  - Base, Barracks, Resource added for visual verification");
        }

        private static void AddPrefabInstance(string name, Vector3 position, string prefabGUID)
        {
            string prefabPath = AssetDatabase.GUIDToAssetPath(prefabGUID);
            if (string.IsNullOrEmpty(prefabPath))
            {
                Debug.LogWarning($"Could not find prefab with GUID {prefabGUID}");
                return;
            }

            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            if (prefab == null)
            {
                Debug.LogWarning($"Could not load prefab at {prefabPath}");
                return;
            }

            GameObject instance = PrefabUtility.InstantiatePrefab(prefab) as GameObject;
            if (instance != null)
            {
                instance.name = name;
                instance.transform.position = position;
                Debug.Log($"✓ Added {name} at {position}");
            }
        }

        [MenuItem("RTS/Visual-2T/Clear VisualPreview Scene", priority = 2)]
        public static void ClearVisualPreview()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
                return;

            var scene = EditorSceneManager.OpenScene(VisualPreviewScenePath, OpenSceneMode.Single);

            // Find and delete all game objects except camera and light
            var rootObjects = scene.GetRootGameObjects();
            foreach (var obj in rootObjects)
            {
                if (obj.name != "Main Camera" && obj.name != "Directional Light")
                    Object.DestroyImmediate(obj);
            }

            EditorSceneManager.SaveScene(scene);
            Debug.Log("✓ VisualPreview scene cleared (kept Camera and Light)");
        }
    }
}
