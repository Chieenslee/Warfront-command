@echo off
echo Installing PyInstaller...
pip install pyinstaller

echo Building Warfront Command as a single executable...
pyinstaller --name "Warfront Command" --windowed --onefile --add-data "warfront/assets;warfront/assets" warfront/__main__.py --noconfirm

echo Cleaning up temporary build files...
rmdir /s /q build
del /q "Warfront Command.spec"
rmdir /s /q __pycache__
rmdir /s /q warfront\__pycache__

echo =======================================================
echo Build complete! Your product is: dist\Warfront Command.exe
echo =======================================================
pause
