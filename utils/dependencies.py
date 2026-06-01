# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import os
import site
import subprocess
import sys
import asyncio
import platform
import inspect

dependencies_installed = False
pip_installed = False
httpx_installed = False


class Dependencies:

    @staticmethod
    def check_dependencies() -> bool:
        global dependencies_installed
        global pip_installed
        global httpx_installed

        print("Checking python package httpx installation...")
        try:
            import pip

            print("pip imported from ", inspect.getfile(pip))
            pip_installed = True
        except ImportError as e:
            print(e)
            pip_installed = False

        try:
            import httpx

            print("httpx imported from ", inspect.getfile(httpx))
            httpx_installed = True
        except ImportError as e:
            print(e)
            httpx_installed = False

        dependencies_installed = pip_installed and httpx_installed

        return dependencies_installed

    @staticmethod
    def install_dependencies(force: bool = False):

        async def install_package(package: str, force: bool):

            global dependencies_installed
            dependencies_installed = False

            # ! get Blender Python installation
            # windows
            if platform.system() == "Windows":
                python_exe = os.path.join(sys.prefix, "bin", "python.exe")
            # macOS
            elif platform.system() == "Darwin":
                python_exe = os.path.join(sys.prefix, "bin", "python3.10")
            # linux
            else:
                python_exe = os.path.join(sys.prefix, "bin", "python3")

            # ! install to user site packages and add to sys.path
            site_packages_path = site.getusersitepackages()

            # Debug information
            print(
                "Installing python modules on: ",
                os.name,
                platform.system(),
                platform.release(),
                " in ",
                site_packages_path,
                " Python exe: ",
                python_exe,
            )

            # ! install and upgrade pip
            try:
                import pip

                print("pip imported from ", inspect.getfile(pip))
            except ImportError as e:
                print(e)
                print("Could not find pip, installing...")
                subprocess.call([python_exe, "-m", "ensurepip", "--user"])
                subprocess.call(
                    [python_exe, "-m", "pip", "install", "--upgrade", "pip", "--user"]
                )

            # ! install package
            if force or not Dependencies.check_dependencies():
                try:
                    subprocess.call(
                        [
                            python_exe,
                            "-m",
                            "pip",
                            "install",
                            "--upgrade",
                            package,
                            "--user",
                        ]
                    )
                    dependencies_installed = True
                except Exception as e:
                    print(e)
                    print(f"Error installing python package {package}.")
                    dependencies_installed = False

            # Add site packages path to sys.path
            if (
                os.path.exists(site_packages_path)
                and site_packages_path not in sys.path
            ):
                sys.path.append(site_packages_path)

        # Run the one-shot install coroutine on a dedicated loop. Do NOT use
        # asyncio.get_event_loop(): the agent runtime now owns a loop on a
        # background thread, the main thread has none, and on Python 3.13
        # get_event_loop() no longer auto-creates one (raises RuntimeError).
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(install_package("httpx==0.24.0", force))
        finally:
            loop.close()
