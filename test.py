import sys
import os
import subprocess
from pathlib import Path

# Usamos el bloc de notas para simular FactoryGame_real.exe
DUMMY_EXE = "notepad.exe"

def test_process_launch():
    print("--- Probando lanzamiento de subproceso simulado ---")
    
    # Simulamos pasar argumentos como si vinieran de Steam
    fake_steam_args = ["--simulated-flag", "test_file.txt"]
    cmd = [DUMMY_EXE] + fake_steam_args
    
    print(f"Lanzando: {cmd}")
    print("Se abrirá un Bloc de Notas. Ciérralo a mano para comprobar que el script espera...")
    
    process = subprocess.Popen(cmd)
    process.wait()
    
    print(f"Proceso cerrado con código de salida: {process.returncode}")
    print("Comprobación de subprocess completada con éxito.")

if __name__ == "__main__":
    test_process_launch()