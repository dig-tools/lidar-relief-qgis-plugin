import os
import glob

# Files to update
files = glob.glob('/home/mark/Projects/LiDAR-Relief-QGIS-Plugin/lidar_relief/algorithms/*_algorithm.py')

for filepath in files:
    with open(filepath, 'r') as f:
        content = f.read()

    # Skip files that already have it or don't need it
    if 'ReliefLayerPostProcessor' in content or 'batch_algorithm' in filepath or 'ml_export' in filepath:
        continue

    # 1. Add import at the top
    # Find the last import from ..core...
    lines = content.split('\n')
    import_idx = -1
    for i, line in enumerate(lines):
        if line.startswith('from ..core.'):
            import_idx = i
            
    if import_idx != -1:
        lines.insert(import_idx + 1, 'from ..styling import ReliefLayerPostProcessor')
    
    content = '\n'.join(lines)

    # 2. Add post processor block before the final return
    # Usually it's:
    #         if feedback.isCanceled():
    #             return {}
    # 
    #         return {self.OUTPUT: output_path}
    
    # Extract the algorithm name from the class name or display name to pass to PostProcessor
    # Let's just pass self.displayName()
    
    block = """
        if context.willLoadLayerOnCompletion(output_path):
            details = context.layerToLoadOnCompletionDetails(output_path)
            details.setPostProcessor(
                ReliefLayerPostProcessor(self.displayName(), stretch_type="stddev")
            )

        return {self.OUTPUT: output_path}"""
        
    content = content.replace('        return {self.OUTPUT: output_path}', block)
    
    with open(filepath, 'w') as f:
        f.write(content)
        
    print(f"Updated {filepath}")
