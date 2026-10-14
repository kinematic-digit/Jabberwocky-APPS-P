# =====================================================================
# JABBERWOCKY ECOSYSTEM — PRODUCTION COMPILER & RELEASER
# VERSION: 2.0.0
# Location: tools/jwp_build.py
# =====================================================================
import os
import sys

class JabberwockyCompiler:
    def __init__(self, source_dir, dist_dir):
        self.source_dir = source_dir
        self.dist_dir = dist_dir

    def compile_release_package(self, output_filename):
        """Bundles bite-sized development profiles into a hyper-optimized release asset."""
        if not os.path.exists(self.dist_dir):
            os.makedirs(self.dist_dir)

        output_path = os.path.join(self.dist_dir, output_filename)
        print(f"🛠️ Compiling Release: Flattening '{self.source_dir}' ➔ '{output_path}'...")

        if not os.path.exists(self.source_dir):
            print(f"❌ ERROR: Source directory '{self.source_dir}' does not exist.")
            return False

        release_content = [
            f"# =====================================================================\n",
            f"# JABBERWOCKY PRODUCTION PROFILE — OPTIMIZED FOR END-USER DEPLOYMENT\n",
            f"# WARNING: Generated file. Do not edit directly. Modify source files instead.\n",
            f"# =====================================================================\n\n"
        ]

        # Scan folder layout structures sequentially to maintain macro parsing order
        for root, _, files in os.walk(self.source_dir):
            for file in sorted(files):
                if file.endswith(".cfg"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r") as src:
                        for line in src:
                            cleaned = line.strip()
                            
                            # --- PERFORMANCE STRIPPING ENGINE ---
                            # Remove dead whitespace rows to compress Klipper's boot parser memory
                            if not cleaned and not line.startswith("#"):
                                continue
                                
                            # Maintain critical operator note tags but drop generic formatting lines
                            if line.startswith("#") and len(cleaned) < 3:
                                continue
                                
                            release_content.append(line)

        with open(output_path, "w") as out:
            out.writelines(release_content)
            
        print(f"🚀 Success: Optimized production asset generated cleanly ({len(release_content)} compiled rows).")
        return True

if __name__ == "__main__":
    # Example execution paths for compiling separate product modules
    print("📦 Initializing Jabberwocky Compilation Pipeline...")
    
    # Pack Toolhead Release
    jwt_compiler = JabberwockyCompiler("config_src/jwt_toolhead", "jabberwocky_release")
    jwt_compiler.compile_release_package("jwt_production.cfg")
    
    # Pack Probe Release
    jwp_compiler = JabberwockyCompiler("config_src/jwp_probe", "jabberwocky_release")
    jwp_compiler.compile_release_package("jwp_production.cfg")
