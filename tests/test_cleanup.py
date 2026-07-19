import asyncio
from pathlib import Path
import sys

# Add project root to sys.path to allow running 'python tests/test_cleanup.py'
# This ensures Python can find the 'app' package
sys.path.append(str(Path(__file__).parent.parent))

# Load .env from the project root directory (parent of 'tests')

from app.modules.pms.storage.base_storage import CloudinaryImageStorage

async def run_test():
    print("Starting local Cloudinary cleanup test...")
    storage = CloudinaryImageStorage()
    await storage.clean_old_temp_images()
    print("Cleanup test finished.")

if __name__ == "__main__":
    asyncio.run(run_test())
