import os
import re
import codecs
import inspect

import ConfigParser
from ConfigParser import SafeConfigParser


class Section(object):
    class Type(object):
        normal = 0
        dict = 1

    _required = False
    _type = Type.normal

class Option(object):
    class Type(object):
        normal = 0
        file = 1
        list = 2

    def __init__(self, type = Type.normal, required = True, value = None):
        self.type = type
        self._required = required
        self.value = value

class INIConfig(object):
    __content = None

    def serialize(self, configFilepath):
        self.configFilepath = configFilepath
        self.config = self._parseConfig()
        self._serialize(self.config)
        # self._checkFilesSection()
        
        
    def save(self):
        dir = os.path.split(self.configFilepath)[0]

        if not os.path.exists(dir):
            os.makedirs(dir)
            
        sections = self._getSections()
        
        for section in sections:
            sectionName = section[0]
            options = section[1].__dict__.items()
            options = filter(
                lambda x: 
                    not str(x[0]).startswith('_')
                    and not str(x[0]).startswith('__'), 
                options)
                
            for option in options:
                optionName = option[0]
                value = option[1]
                self.config.set(sectionName, optionName, value)
                
        with open(self.configFilepath, 'wb') as f:
            self.config.write(f)


    def isSectionExistsAndNotEmpty(self, sectionName):
        if (sectionName in self.config.sections() and
            len(self.config.options(sectionName)) != 0):
            return True

        return False


    def getLineNumber(self, sectionObject, optionString):
        sectionName = self._getSectionName(sectionObject)
        sectionBegin = self._getSectionBegin(sectionName)

        if sectionBegin != None:
            sectionEnd = self._getSectionEnd(sectionBegin)

            for i in range(sectionBegin, sectionEnd):
                line = self.__content[i].replace('\n', '').replace('\r', '')

                if not line.startswith('#') and optionString in line:
                    return i + 1

        return None

    def _getSectionBegin(self, sectionName):
        section = '[%s]' % sectionName
        
        for i, line in enumerate(self.__content):
            line = line.replace('\r', '').replace('\n', '')
            if line == section:
                return i + 1

        return None


    def _getSectionEnd(self, sectionBegin):
        contentEnd = len(self.__content)

        for i in range(sectionBegin, contentEnd):
            line = self.__content[i].replace('\r', '').replace('\n', '')

            if re.match('\[.+\]', line):
                return i

        return contentEnd


    def _parseConfig(self):
        config = SafeConfigParser(allow_no_value = True)
        config.optionxform = str

        try:
            with codecs.open(self.configFilepath, 'r', 'utf-8-sig') as f:
                config.readfp(f)
                f.seek(0)
                self.__content = f.readlines()
        except UnicodeDecodeError as e:
            msg = '"%s" must be in UTF-8 encoding. ' \
                'The use of the BOM is discouraged.' % self.configFilepath
            raise UnicodeError(msg)

        return config


    def _getSections(self):
        sections = inspect.getmembers(self, lambda x: not(inspect.isroutine(x)))
        sections = filter(
            lambda x: 
                not str(x[0]).startswith('__')
                and type(getattr(self, x[0])) == type, 
            sections)

        return sections


    def _removeMissingButNotRequiredSections(self, sections, config):
        formatedSections = []
        for sectionName, section in sections:
            if not section._required and sectionName not in config.sections():
                setattr(self, sectionName, None)
            else:
                formatedSections.append((sectionName, section))

        return formatedSections


    def _checkMissingSections(self, sections, config):
        for section in sections:
            sectionName = section[0]
            section = section[1]

            if section._required:
                try:
                    config.items(sectionName)
                except ConfigParser.NoSectionError as e:
                    e.message += ' in config file "%s"' % self.configFilepath
                    raise e


    def _checkOptions(self, sectionName, options, config):
        for optionName, option in options:
            if option._required:
                try:
                    config.get(sectionName, optionName)
                except ConfigParser.NoOptionError as e:
                    e.message += ' in config file "%s"' % self.configFilepath
                    raise e


    def _removeMissingButNotRequiredOptions(self, sectionName, section, options, config):
        formatedOptions = []

        for optionName, option in options:
            if not option._required and optionName not in config.options(sectionName):
                setattr(section, optionName, None)
            else:
                formatedOptions.append((optionName, option))

        return formatedOptions


    def _setOptionValues(self, section, sectionName, options, config):
        for optionName, option in options:
            value = config.get(sectionName, optionName)

            if option.type == Option.Type.file:
                filepath = self._getRelativePath(value, self.configDirpath)
                self._checkFileExistance(filepath, sectionName, optionName)
                value = filepath

            elif option.type == Option.Type.list:
                value = value.split(',')
                value = [v.lstrip(' ') for v in value]
                
            setattr(section, optionName, value)


    def _setSectionValues(self, sections, config):
        for sectionName, section in sections:
            if section._type == Section.Type.dict:
                if sectionName in config.sections():
                    optionsValuesDict = config.items(sectionName)
                    setattr(self, sectionName, optionsValuesDict)
                else:
                    setattr(self, sectionName, None)

                continue

            options = filter(lambda x: type(x[1]) == Option, section.__dict__.items())
            self._checkOptions(sectionName, options, config)
            options = self._removeMissingButNotRequiredOptions(sectionName, section, options, config)
            self._setOptionValues(section, sectionName, options, config)


    def _serialize(self, config):
        sections = self._getSections()
        self._checkMissingSections(sections, config)
        sections = self._removeMissingButNotRequiredSections(sections, config)
        self._setSectionValues(sections, config)


    def _getRelativePath(self, path, pathRelativeTo):
        relativePath = os.path.join(pathRelativeTo, path)
        relativePath = os.path.normpath(relativePath)

        return relativePath


    def _getSectionName(self, sectionObject):
        sections = inspect.getmembers(self, lambda x: not(inspect.isroutine(x)))
        section = filter(lambda x: x[1] == sectionObject, sections)
        sectionName = section[0][0]
        
        return sectionName


    def _getOptionName(self, sectionObject, optionObject):
        options = inspect.getmembers(sectionObject, lambda x: not(inspect.isroutine(x)))
        option = filter(lambda x: x[1] == optionObject, options)
        optionName = option[0][0]
        
        return optionName
