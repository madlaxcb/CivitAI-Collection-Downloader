
import sys
import traceback
import os

def main():
    try:
        # Set TCL/TK environment variables for PyInstaller one-file mode
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            os.environ['TCL_LIBRARY'] = os.path.join(base_path, 'lib', 'tcl8.6')
            os.environ['TK_LIBRARY'] = os.path.join(base_path, 'lib', 'tk8.6')
            print(f"Set TCL_LIBRARY to: {os.environ['TCL_LIBRARY']}")
            print(f"Set TK_LIBRARY to: {os.environ['TK_LIBRARY']}")

        # Diagnostic: Check environment
        print("Diagnostic: Checking environment...")
        print(f"sys.executable: {sys.executable}")
        print(f"sys.path: {sys.path}")
        
        try:
            import tkinter
            print(f"tkinter imported: {tkinter}")
            try:
                print(f"tkinter file: {tkinter.__file__}")
            except:
                pass
            print(f"TkVersion: {tkinter.TkVersion}")
        except ImportError as e:
            print(f"Diagnostic: Failed to import tkinter: {e}")
        except Exception as e:
            print(f"Diagnostic: Error importing tkinter: {e}")

        # Import the main application logic here
        # This will trigger all the top-level code in gui.py and its dependencies
        import gui
        gui.main()
    except BaseException:
        print("\n\n" + "="*50)
        print("CRITICAL LAUNCH ERROR CAUGHT BY LAUNCHER")
        print("="*50)
        traceback.print_exc()
        print("="*50)
        
        # Also try to write to a file in the same directory as the executable
        try:
            exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            log_path = os.path.join(exe_dir, "launcher_crash.log")
            with open(log_path, "w") as f:
                f.write(traceback.format_exc())
            print(f"Crash log saved to: {log_path}")
        except Exception as e:
            print(f"Failed to write log file: {e}")

        print("\nPress Enter to exit...")
        try:
            input()
        except Exception:
            pass

if __name__ == "__main__":
    main()
