using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.TeacherConversion
{
    public sealed class Stage7BTeacherSampleLoader
    {
        public bool TryLoadPreviewJsonLines(string filePath, out int sampleCount, out string diagnostics)
        {
            sampleCount = 0;
            diagnostics = string.Empty;

            if (string.IsNullOrWhiteSpace(filePath) || !File.Exists(filePath))
            {
                diagnostics = "Preview JSONL file is missing.";
                return false;
            }

            try
            {
                using var reader = new StreamReader(filePath);
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    if (!string.IsNullOrWhiteSpace(line))
                    {
                        sampleCount++;
                    }
                }

                diagnostics = "Loaded preview rows count only; full runtime reconstruction is not attempted in this stage.";
                return true;
            }
            catch (System.Exception ex)
            {
                diagnostics = ex.Message;
                return false;
            }
        }
    }
}
