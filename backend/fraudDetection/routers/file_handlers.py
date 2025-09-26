# utils/file_handler.py
from datetime import datetime
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException, status
from PIL import Image
import magic
import hashlib
# File upload router endpoint
from fastapi import APIRouter, Depends, File, UploadFile
from .authentication import get_current_user
from ..models import User

# Configuration
UPLOAD_DIR = Path("uploads")
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_IMAGE_TYPES = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp'
}

# Ensure upload directory exists
UPLOAD_DIR.mkdir(exist_ok=True)
(UPLOAD_DIR / "deposits").mkdir(exist_ok=True)
(UPLOAD_DIR / "withdrawals").mkdir(exist_ok=True)
(UPLOAD_DIR / "temp").mkdir(exist_ok=True)


def validate_image_file(file: UploadFile) -> bool:
    """Validate that the uploaded file is a valid image."""
    try:
        # Check file size
        if file.size and file.size > MAX_FILE_SIZE:
            return False
        
        # Reset file pointer
        file.file.seek(0)
        
        # Read first chunk to detect file type
        chunk = file.file.read(1024)
        file.file.seek(0)
        
        # Use python-magic to detect actual file type
        mime_type = magic.from_buffer(chunk, mime=True)
        
        # Check if it's an allowed image type
        if mime_type not in ALLOWED_IMAGE_TYPES:
            return False
        
        # Additional validation with PIL
        try:
            with Image.open(file.file) as img:
                img.verify()
            file.file.seek(0)  # Reset after verification
            return True
        except Exception:
            return False
            
    except Exception:
        return False


def generate_secure_filename(original_filename: str, user_id: int, file_type: str = "deposit") -> str:
    """Generate a secure filename for uploaded files."""
    # Get file extension from original filename
    original_ext = Path(original_filename).suffix.lower()
    
    # Generate unique identifier
    unique_id = str(uuid.uuid4())
    timestamp = str(int(datetime.now().timestamp()))
    
    # Create secure filename
    filename = f"{file_type}_{user_id}_{timestamp}_{unique_id}{original_ext}"
    
    return filename


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


async def save_uploaded_file(
    file: UploadFile, 
    file_type: str, 
    user_id: int,
    compress_image: bool = True
) -> str:
    """
    Save uploaded file to disk with validation and optional compression.
    
    Args:
        file: The uploaded file
        file_type: Type of file (e.g., 'deposits', 'withdrawals')
        user_id: ID of the user uploading the file
        compress_image: Whether to compress the image
    
    Returns:
        str: URL path to the saved file
    
    Raises:
        HTTPException: If file validation fails or saving fails
    """
    try:
        # Validate file
        if not validate_image_file(file):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image file"
            )
        
        # Generate secure filename
        secure_filename = generate_secure_filename(file.filename, user_id, file_type)
        
        # Create file path
        file_dir = UPLOAD_DIR / file_type
        file_dir.mkdir(exist_ok=True)
        
        file_path = file_dir / secure_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Optional image compression and optimization
        if compress_image:
            await optimize_image(file_path)
        
        # Calculate file hash for integrity verification
        file_hash = calculate_file_hash(file_path)
        
        # Store file metadata (you might want to save this to database)
        file_metadata = {
            'original_filename': file.filename,
            'secure_filename': secure_filename,
            'file_path': str(file_path),
            'file_size': file_path.stat().st_size,
            'mime_type': file.content_type,
            'file_hash': file_hash,
            'user_id': user_id,
            'upload_timestamp': datetime.now().isoformat()
        }
        
        # Return URL path (adjust based on your static file serving setup)
        return f"uploads/{file_type}/{secure_filename}"
        
    except HTTPException:
        raise
    except Exception as e:
        # Clean up file if it was partially saved
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )


async def optimize_image(file_path: Path, max_width: int = 1920, max_height: int = 1080, quality: int = 85) -> None:
    """
    Optimize image by resizing and compressing.
    
    Args:
        file_path: Path to the image file
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
        quality: JPEG quality (1-100)
    """
    try:
        with Image.open(file_path) as img:
            # Convert RGBA to RGB if necessary (for JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Calculate new size maintaining aspect ratio
            original_width, original_height = img.size
            
            if original_width > max_width or original_height > max_height:
                ratio = min(max_width / original_width, max_height / original_height)
                new_width = int(original_width * ratio)
                new_height = int(original_height * ratio)
                
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save optimized image
            img.save(file_path, optimize=True, quality=quality)
            
    except Exception as e:
        # Log the error but don't fail the upload
        print(f"Image optimization failed: {str(e)}")


def delete_file(file_path: str) -> bool:
    """
    Delete a file from the filesystem.
    
    Args:
        file_path: Path to the file to delete
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False
    except Exception:
        return False


def get_file_info(file_path: str) -> Optional[dict]:
    """
    Get information about a file.
    
    Args:
        file_path: Path to the file
    
    Returns:
        dict: File information or None if file doesn't exist
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        
        stat = path.stat()
        return {
            'filename': path.name,
            'size': stat.st_size,
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'is_file': path.is_file(),
            'extension': path.suffix
        }
    except Exception:
        return None




upload_router = APIRouter(prefix="/upload", tags=["upload"])

@upload_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = "temp",
    current_user: User = Depends(get_current_user)
):
    """Upload a file."""
    try:
        file_url = await save_uploaded_file(file, file_type, current_user.id)
        
        return {
            "success": True,
            "url": file_url,
            "filename": file.filename,
            "size": file.size,
            "content_type": file.content_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )