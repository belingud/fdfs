#!/usr/bin/env python
# -*- coding: utf-8 -*-
# filename: client.py

from fdfs_client.connection import ConnectionPool
from fdfs_client.exceptions import DataError, ResponseError, ConfigError
from fdfs_client.fdfs_protol import STORAGE_SET_METADATA_FLAG_OVERWRITE
from fdfs_client.storage_client import Storage_client
from fdfs_client.tracker_client import Tracker_client
from fdfs_client.utils import Fdfs_ConfigParser, split_remote_fileid, fdfs_check_file


def get_tracker_conf(conf_path="client.conf"):
    tracker = {}
    cf = Fdfs_ConfigParser()
    cf.read(conf_path)
    timeout = cf.getint("__config__", "connect_timeout")
    tracker_server = cf.get("__config__", "tracker_server")
    if not tracker_server:
        raise ConfigError('You have to set `tracker_server` in `{}`'.format(conf_path))
    tracker_list = tracker_server.split(',')
    tracker_ip_set = set()
    for tr in tracker_list:
        tracker_ip, tracker_port = tr.split(":")
        tracker_ip_set.add((tracker_ip, int(tracker_port)))
    tracker["host_tuple"] = tuple(tracker_ip_set)
    tracker["timeout"] = timeout
    tracker["name"] = "Tracker Pool"
    return tracker


class Fdfs_client(object):
    """
    Class Fdfs_client implemented Fastdfs client protol ver 3.08.

    It's useful upload, download, delete file to or from fdfs server, etc. It's uses
    connection pool to manage connection to server.
    """

    def __init__(self, conf_path="/etc/fdfs/client.conf", pool_class=ConnectionPool, debug=False):
        self.trackers = get_tracker_conf(conf_path)
        self.tracker_pool = pool_class(**self.trackers)
        self.timeout = self.trackers["timeout"]
        self.storages = {}
        self.debug = debug

    def __del__(self):
        try:
            self.tracker_pool.destroy()
            self.tracker_pool = None
        except Exception:
            pass

    def get_storage(self, store_serv):
        store = self.storages.get((store_serv.ip_addr, store_serv.port), None)
        if store is None:
            store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
            self.storages[(store_serv.ip_addr, store_serv.port)] = store
        return store

    def get_store_serv(self, remote_file_id):
        """
        Get store server info by remote_file_id.
        @author: LeoTse
        @param remote_file_id: string, file_id of file that is on storage server
        @return Storage_server object
        """
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(in delete file)")
        group_name, remote_filename = tmp
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, remote_filename)
        return store_serv

    def upload_by_filename(self, filename, meta_dict=None):
        """
        Upload a file to Storage server.
        arguments:
        @filename: string, name of file that will be uploaded
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        } meta_dict can be null
        @return dict {
            'Group name'      : group_name,
            'Remote file_id'  : remote_file_id,
            'Status'          : 'Upload successed.',
            'Local file name' : local_file_name,
            'Uploaded size'   : upload_size,
            'Storage IP'      : storage_ip
        } if success else None
        """
        isfile, errmsg = fdfs_check_file(filename)
        if not isfile:
            raise DataError(errmsg + "(uploading)")
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        return self.get_storage(store_serv).storage_upload_by_filename(
            tc, store_serv, filename, meta_dict
        )

    def upload_by_file(self, filename, meta_dict=None):
        isfile, errmsg = fdfs_check_file(filename)
        if not isfile:
            raise DataError(errmsg + "(uploading)")
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        return self.get_storage(store_serv).storage_upload_by_file(
            tc, store_serv, filename, meta_dict
        )

    def upload_by_buffer(self, filebuffer, file_ext_name=None, meta_dict=None):
        """
        Upload a buffer to Storage server.
        arguments:
        @filebuffer: string, buffer
        @file_ext_name: string, file extend name
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }
        @return dict {
            'Group name'      : group_name,
            'Remote file_id'  : remote_file_id,
            'Status'          : 'Upload successed.',
            'Local file name' : '',
            'Uploaded size'   : upload_size,
            'Storage IP'      : storage_ip
        } if success else None
        """
        if not filebuffer:
            raise DataError("[-] Error: argument filebuffer can not be null.")
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        return self.get_storage(store_serv).storage_upload_by_buffer(
            tc, store_serv, filebuffer, file_ext_name, meta_dict
        )

    def upload_slave_by_filename(
        self, filename, remote_file_id, prefix_name, meta_dict=None
    ):
        """
        Upload slave file to Storage server.
        arguments:
        @filename: string, local file name
        @remote_file_id: string, remote file id
        @prefix_name: string
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }
        @return dictionary {
            'Status'        : 'Upload slave successed.',
            'Local file name' : local_filename,
            'Uploaded size'   : upload_size,
            'Remote file id'  : remote_file_id,
            'Storage IP'      : storage_ip
        }
        """
        isfile, errmsg = fdfs_check_file(filename)
        if not isfile:
            raise DataError(errmsg + "(uploading slave)")
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(uploading slave)")
        if not prefix_name:
            raise DataError("[-] Error: prefix_name can not be null.")
        group_name, remote_filename = tmp
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_with_group(group_name)
        store = self.get_storage(store_serv)
        try:
            ret_dict = store.storage_upload_slave_by_filename(
                tc, store_serv, filename, prefix_name, remote_filename, meta_dict=None
            )
        except Exception:
            raise
        ret_dict["Status"] = "Upload slave file successed."
        return ret_dict

    def upload_slave_by_file(
        self, filename, remote_file_id, prefix_name, meta_dict=None
    ):
        """
        Upload slave file to Storage server.
        arguments:
        @filename: string, local file name
        @remote_file_id: string, remote file id
        @prefix_name: string
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }
        @return dictionary {
            'Status'        : 'Upload slave successed.',
            'Local file name' : local_filename,
            'Uploaded size'   : upload_size,
            'Remote file id'  : remote_file_id,
            'Storage IP'      : storage_ip
        }
        """
        isfile, errmsg = fdfs_check_file(filename)
        if not isfile:
            raise DataError(errmsg + "(uploading slave)")
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(uploading slave)")
        if not prefix_name:
            raise DataError("[-] Error: prefix_name can not be null.")
        group_name, remote_filename = tmp
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_with_group(group_name)
        store = self.get_storage(store_serv)
        try:
            ret_dict = store.storage_upload_slave_by_file(
                tc, store_serv, filename, prefix_name, remote_filename, meta_dict=None
            )
        except:
            raise
        ret_dict["Status"] = "Upload slave file successed."
        return ret_dict

    def upload_slave_by_buffer(
        self, filebuffer, remote_file_id, meta_dict=None, file_ext_name=None
    ):
        """
        Upload slave file by buffer
        arguments:
        @filebuffer: string
        @remote_file_id: string
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }
        @return dictionary {
            'Status'        : 'Upload slave successed.',
            'Local file name' : local_filename,
            'Uploaded size'   : upload_size,
            'Remote file id'  : remote_file_id,
            'Storage IP'      : storage_ip
        }
        """
        if not filebuffer:
            raise DataError("[-] Error: argument filebuffer can not be null.")
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(uploading slave)")
        group_name, remote_filename = tmp
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, remote_filename)
        store = self.get_storage(store_serv)
        return store.storage_upload_slave_by_buffer(
            tc, store_serv, filebuffer, remote_filename, meta_dict, file_ext_name
        )

    def upload_appender_by_filename(self, local_filename, meta_dict=None):
        """
        Upload an appender file by filename.
        arguments:
        @local_filename: string
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }    Notice: it can be null
        @return dict {
            'Group name'      : group_name,
            'Remote file_id'  : remote_file_id,
            'Status'          : 'Upload successed.',
            'Local file name' : '',
            'Uploaded size'   : upload_size,
            'Storage IP'      : storage_ip
        } if success else None
        """
        isfile, errmsg = fdfs_check_file(local_filename)
        if not isfile:
            raise DataError(errmsg + "(uploading appender)")
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        store = self.get_storage(store_serv)
        return store.storage_upload_appender_by_filename(
            tc, store_serv, local_filename, meta_dict
        )

    def upload_appender_by_file(self, local_filename, meta_dict=None):
        """
        Upload an appender file by file.
        arguments:
        @local_filename: string
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }    Notice: it can be null
        @return dict {
            'Group name'      : group_name,
            'Remote file_id'  : remote_file_id,
            'Status'          : 'Upload successed.',
            'Local file name' : '',
            'Uploaded size'   : upload_size,
            'Storage IP'      : storage_ip
        } if success else None
        """
        isfile, errmsg = fdfs_check_file(local_filename)
        if not isfile:
            raise DataError(errmsg + "(uploading appender)")
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        store = self.get_storage(store_serv)
        return store.storage_upload_appender_by_file(
            tc, store_serv, local_filename, meta_dict
        )

    def upload_appender_by_buffer(self, filebuffer, file_ext_name=None, meta_dict=None):
        """
        Upload a buffer to Storage server.
        arguments:
        @filebuffer: string
        @file_ext_name: string, can be null
        @meta_dict: dictionary, can be null
        @return dict {
            'Group name'      : group_name,
            'Remote file_id'  : remote_file_id,
            'Status'          : 'Upload successed.',
            'Local file name' : '',
            'Uploaded size'   : upload_size,
            'Storage IP'      : storage_ip
        } if success else None
        """
        if not filebuffer:
            raise DataError("[-] Error: argument filebuffer can not be null.")
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        store = self.get_storage(store_serv)
        return store.storage_upload_appender_by_buffer(
            tc, store_serv, filebuffer, meta_dict, file_ext_name
        )

    def delete_file(self, remote_file_id):
        """
        Delete a file from Storage server.
        arguments:
        @remote_file_id: string, file_id of file that is on storage server
        @return tuple ('Delete file successed.', remote_file_id, storage_ip)
        """
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(in delete file)")
        group_name, remote_filename = tmp
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, remote_filename)
        store = self.get_storage(store_serv)
        return store.storage_delete_file(tc, store_serv, remote_filename)

    def download_to_file(self, local_filename, remote_file_id, offset=0, down_bytes=0):
        """
        Download a file from Storage server.
        arguments:
        @local_filename: string, local name of file
        @remote_file_id: string, file_id of file that is on storage server
        @offset: long
        @downbytes: long
        @return dict {
            'Remote file_id'  : remote_file_id,
            'Content'         : local_filename,
            'Download size'   : downloaded_size,
            'Storage IP'      : storage_ip
        }
        """
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(in download file)")
        group_name, remote_filename = tmp
        if not offset:
            file_offset = offset
        if not down_bytes:
            download_bytes = down_bytes
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_fetch(group_name, remote_filename)
        store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_download_to_file(
            tc, store_serv, local_filename, file_offset, download_bytes, remote_filename
        )

    def download_to_buffer(self, remote_file_id, offset=0, down_bytes=0):
        """
        Download a file from Storage server and store in buffer.
        arguments:
        @remote_file_id: string, file_id of file that is on storage server
        @offset: long
        @down_bytes: long
        @return dict {
            'Remote file_id'  : remote_file_id,
            'Content'         : file_buffer,
            'Download size'   : downloaded_size,
            'Storage IP'      : storage_ip
        }
        """
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(in download file)")
        group_name, remote_filename = tmp
        if not offset:
            file_offset = offset
        if not down_bytes:
            download_bytes = down_bytes
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_fetch(group_name, remote_filename)
        store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
        file_buffer = None
        return store.storage_download_to_buffer(
            tc, store_serv, file_buffer, file_offset, download_bytes, remote_filename
        )

    def list_one_group(self, group_name):
        """
        List one group information.
        arguments:
        @group_name: string, group name will be list
        @return Group_info,  instance
        """
        tc = Tracker_client(self.tracker_pool)
        return tc.tracker_list_one_group(group_name)

    def list_servers(self, group_name, storage_ip=None):
        """
        List all storage servers information in a group
        arguments:
        @group_name: string
        @return dictionary {
            'Group name' : group_name,
            'Servers'    : server list,
        }
        """
        tc = Tracker_client(self.tracker_pool)
        return tc.tracker_list_servers(group_name, storage_ip)

    def list_all_groups(self):
        """
        List all group information.
        @return dictionary {
            'Groups count' : group_count,
            'Groups'       : list of groups
        }
        """
        tc = Tracker_client(self.tracker_pool)
        return tc.tracker_list_all_groups()

    def get_meta_data(self, remote_file_id):
        """
        Get meta data of remote file.
        arguments:
        @remote_fileid: string, remote file id
        @return dictionary, meta data
        """
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(in get meta data)")
        group_name, remote_filename = tmp
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, remote_filename)
        store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_get_metadata(tc, store_serv, remote_filename)

    def set_meta_data(
        self, remote_file_id, meta_dict, op_flag=STORAGE_SET_METADATA_FLAG_OVERWRITE
    ):
        """
        Set meta data of remote file.
        arguments:
        @remote_file_id: string
        @meta_dict: dictionary
        @op_flag: char, 'O' for overwrite, 'M' for merge
        @return dictionary {
            'Status'     : status,
            'Storage IP' : storage_ip
        }
        """
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(in set meta data)")
        group_name, remote_filename = tmp
        tc = Tracker_client(self.tracker_pool)
        try:
            store_serv = tc.tracker_query_storage_update(group_name, remote_filename)
            store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
            status = store.storage_set_metadata(
                tc, store_serv, remote_filename, meta_dict
            )
        except (ConnectionError, ResponseError, DataError):
            raise
        # if status == 2:
        #    raise DataError('[-] Error: remote file %s is not exist.' % remote_file_id)
        if status != 0:
            raise DataError("[-] Error: %d, %s" % (status, os.strerror(status)))
        ret_dict = {
            "Status": "Set meta data success.",
            "Storage IP": store_serv.ip_addr,
        }
        return ret_dict

    def append_by_filename(self, local_filename, remote_fileid):
        isfile, errmsg = fdfs_check_file(local_filename)
        if not isfile:
            raise DataError(errmsg + "(append)")
        tmp = split_remote_fileid(remote_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(append)")
        group_name, appended_filename = tmp
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appended_filename)
        store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_append_by_filename(
            tc, store_serv, local_filename, appended_filename
        )

    def append_by_file(self, local_filename, remote_fileid):
        isfile, errmsg = fdfs_check_file(local_filename)
        if not isfile:
            raise DataError(errmsg + "(append)")
        tmp = split_remote_fileid(remote_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(append)")
        group_name, appended_filename = tmp
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appended_filename)
        store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_append_by_file(
            tc, store_serv, local_filename, appended_filename
        )

    def append_by_buffer(self, file_buffer, remote_fileid):
        if not file_buffer:
            raise DataError("[-] Error: file_buffer can not be null.")
        tmp = split_remote_fileid(remote_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(append)")
        group_name, appended_filename = tmp
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appended_filename)
        store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_append_by_buffer(
            tc, store_serv, file_buffer, appended_filename
        )

    def truncate_file(self, truncated_filesize, appender_fileid):
        """
        Truncate file in Storage server.
        arguments:
        @truncated_filesize: long
        @appender_fileid: remote_fileid
        @return: dictionary {
            'Status'     : 'Truncate successed.',
            'Storage IP' : storage_ip
        }
        """
        trunc_filesize = truncated_filesize
        tmp = split_remote_fileid(appender_fileid)
        if not tmp:
            raise DataError("[-] Error: appender_fileid is invalid.(truncate)")
        group_name, appender_filename = tmp
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appender_filename)
        store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_truncate_file(
            tc, store_serv, trunc_filesize, appender_filename
        )

    def modify_by_filename(self, filename, appender_fileid, offset=0):
        """
        Modify a file in Storage server by file.
        arguments:
        @filename: string, local file name
        @offset: long, file offset
        @appender_fileid: string, remote file id
        @return: dictionary {
            'Status'     : 'Modify successed.',
            'Storage IP' : storage_ip
        }
        """
        isfile, errmsg = fdfs_check_file(filename)
        if not isfile:
            raise DataError(errmsg + "(modify)")
        filesize = os.stat(filename).st_size
        tmp = split_remote_fileid(appender_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_fileid is invalid.(modify)")
        group_name, appender_filename = tmp
        if not offset:
            file_offset = offset
        else:
            file_offset = 0
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appender_filename)
        store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_modify_by_filename(
            tc, store_serv, filename, file_offset, filesize, appender_filename
        )

    def modify_by_file(self, filename, appender_fileid, offset=0):
        """
        Modify a file in Storage server by file.
        arguments:
        @filename: string, local file name
        @offset: long, file offset
        @appender_fileid: string, remote file id
        @return: dictionary {
            'Status'     : 'Modify successed.',
            'Storage IP' : storage_ip
        }
        """
        isfile, errmsg = fdfs_check_file(filename)
        if not isfile:
            raise DataError(errmsg + "(modify)")
        filesize = os.stat(filename).st_size
        tmp = split_remote_fileid(appender_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_fileid is invalid.(modify)")
        group_name, appender_filename = tmp
        if not offset:
            file_offset = offset
        else:
            file_offset = 0
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appender_filename)
        store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_modify_by_file(
            tc, store_serv, filename, file_offset, filesize, appender_filename
        )

    def modify_by_buffer(self, filebuffer, appender_fileid, offset=0):
        """
        Modify a file in Storage server by buffer.
        arguments:
        @filebuffer: string, file buffer
        @offset: long, file offset
        @appender_fileid: string, remote file id
        @return: dictionary {
            'Status'     : 'Modify successed.',
            'Storage IP' : storage_ip
        }
        """
        if not filebuffer:
            raise DataError("[-] Error: filebuffer can not be null.(modify)")
        filesize = len(filebuffer)
        tmp = split_remote_fileid(appender_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_fileid is invalid.(modify)")
        group_name, appender_filename = tmp
        if not offset:
            file_offset = offset
        else:
            file_offset = 0
        tc = Tracker_client(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appender_filename)
        store = Storage_client(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_modify_by_buffer(
            tc, store_serv, filebuffer, file_offset, filesize, appender_filename
        )
