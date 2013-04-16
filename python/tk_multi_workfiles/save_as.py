"""
Copyright (c) 2013 Shotgun Software, Inc
----------------------------------------------------
"""
import os
from itertools import chain

import tank
from tank.platform.qt import QtCore, QtGui 
from tank import TankError

from pprint import pprint

from .async_worker import AsyncWorker

class SaveAs(object):
    """
    
    """
    
    @staticmethod
    def show_save_as_dlg(app):
        """
        
        """
        handler = SaveAs(app)
        handler._show_save_as_dlg()
        
    def __init__(self, app):
        """
        Construction
        """
        self._app = app
        
        self._work_template = self._app.get_template("template_work")
        self._publish_template = self._app.get_template("template_publish")
        
        self.generate_new_work_file_path("", False, "", False)
        
    def _show_save_as_dlg(self):
        """
        Show the save as dialog
        """
        
        #self._get_published_file_details()
        #return
        
        # get the current file path:
        current_path = self._get_current_file_path()
        
        # determine if this is a publish path or not:
        is_publish = self._publish_template.validate(current_path)
        fields = {}
        title = "Tank Save As"
        if is_publish:
            fields = self._publish_template.get_fields(current_path)
            title = "Copy to Work Area"
        elif self._work_template.validate(current_path):
            fields = self._work_template.get_fields(current_path)
            title = "Tank Save As"
        name = fields.get("name", "name")
        
        worker_cb = lambda details, wp=current_path, ip=is_publish: self.generate_new_work_file_path(wp, ip, details.get("name"), details.get("reset_version"))
        with AsyncWorker(worker_cb) as preview_updater:
            while True:
                # show modal dialog:
                from .save_as_form import SaveAsForm
                (res, form) = self._app.engine.show_modal(title, self._app, SaveAsForm, preview_updater, is_publish, name)
                
                if res == QtGui.QDialog.Accepted:
                    # get details from UI:
                    name = form.name
                    reset_version = form.reset_version
                    
                    details = self.generate_new_work_file_path(current_path, is_publish, name, reset_version)
                    new_path = details.get("path")
                    msg = details.get("message")
                    
                    if msg:
                        msg = "<b>%s<b><br><br>Are you sure you want to save?" % msg
                        res = QtGui.QMessageBox.question(None, "Confirm", msg, QtGui.QMessageBox.Cancel | QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
                        if res == QtGui.QMessageBox.No:
                            continue
                        elif res == QtGui.QMessageBox.Cancel:
                            break
                        
                    # ok, so do save-as:
                    try:
                        self.save_as(new_path)
                    except Exception, e:
                        self._app.log_exception("Something went wrong while saving!")
                    else:
                        QtGui.QMessageBox.information(None, "Success", "File Succesfully Saved!")
                        
                    break
                else:
                    break
        
    def save_as(self, new_path):
        """
        Do actual save-as of the current scene as the new
        path - assumes all validity checking has already
        been done
        """
        
        # always try to create folders:
        ctx_entity = self._app.context.task if self._app.context.task else self._app.context.entity
        self._app.tank.create_filesystem_structure(ctx_entity.get("type"), ctx_entity.get("id"))
        
        # and save the current file as the new path:
        self._save_current_file_as(new_path)
            
            
    def _save_current_file_as(self, path):
        """
        Use hook to get the current work/scene file path
        """
        self._app.execute_hook("hook_scene_operation", operation="save_as", file_path=path)
        
    def generate_new_work_file_path(self, current_path, current_is_publish, new_name, reset_version):
        """
        Generate a new work file path from the current path taking into
        account existing work files and publishes.
        """
        new_work_path = ""
        msg = None
        can_reset_version = False

        # get fields from current path:
        fields = {}
        base_template = self._publish_template if current_is_publish else self._work_template
        if base_template.validate(current_path):
            fields = base_template.get_fields(current_path)
        else:
            fields["version"] = 1
            
        current_version = fields.get("version")
        current_name = fields.get("name")

        # add in fields from context:
        fields = dict(chain(self._app.context.as_template_fields(self._work_template).iteritems(), fields.iteritems()))

        # update name field:
        fields["name"] = new_name

        # find the current max work file and publish versions:
        from .versioning import Versioning
        versioning = Versioning(self._app)
        max_work_version = versioning.get_max_workfile_version(fields)
        max_publish_version = versioning.get_max_publish_version(new_name)
        max_version = max(max_work_version, max_publish_version)
        
        # now depending on what the source was 
        # and if the name has been changed:
        new_version = None
        if current_is_publish and new_name == current_name:
            # we're ok to just copy publish across and version up
            can_reset_version = False
            new_version = max_version + 1
            
            if new_version != current_version+1:
                #(AD) - do we need a warning here?
                pass
            
            msg = None
        else:
            if max_version:
                # already have a publish and/or work file
                can_reset_version = False
                new_version = max_version + 1
                
                if max_version == max_publish_version:
                    msg = "Because a publish with this name already exists (v%03d), the work file will be saved with the next available version, v%03d" % (max_version, new_version)
                else:
                    msg = "Because a work file with this name already exists (v%03d), the work file will be saved with the next available version, v%03d" % (max_version, new_version)
                
            else:
                # don't have an existing version
                can_reset_version = True
                msg = ""
                if reset_version:
                    new_version = 1
                    
        # now create new path
        if new_version:
            fields["version"] = new_version
        new_work_path = self._work_template.apply_fields(fields)
        
        # check to see if a work file of that version exists:
        #if os.path.exists(new_work_path):
        #    msg = "File already exists!"

        return {"path":new_work_path, "message":msg, "can_reset_version":can_reset_version}
            
        
    def _get_current_file_path(self):
        """
        Use hook to get the current work/scene file path
        """
        return self._app.execute_hook("hook_scene_operation", operation="current_path", file_path="")
    
    
    
    