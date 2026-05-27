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

# pyright: reportInvalidTypeForm=false


import bpy
from bpy.types import Operator
from ..utils.dependencies import Dependencies
from .. import __package__ as base_package


class CHAT_COMPANION_OT_install_deps(Operator):
    bl_idname = "chat_companion.install_deps"
    bl_label = "Install Dependencies"
    bl_description = (
        "Install or Reinstall the python module dependencies for POPAgent"
    )
    bl_options = {"REGISTER", "INTERNAL"}

    # properties
    install_deps: bpy.props.BoolProperty(default=False, options={"HIDDEN"})
    force_install: bpy.props.BoolProperty(default=False, options={"HIDDEN"})

    def execute(self, context):
        if self.install_deps:
            Dependencies.install_dependencies(force=self.force_install)
        else:
            Dependencies.check_dependencies()
            addon_preferences = context.preferences.addons[base_package].preferences
            addon_preferences.dependencies_checked = True

        return {"FINISHED"}
