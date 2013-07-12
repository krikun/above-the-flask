# -*- coding: utf-8 -*-
# WTF? http://stackoverflow.com/questions/5040532/python-ascii-codec-cant-decode-byte
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import os
import libxml2
from flask import Flask, render_template, redirect, url_for, session, request, abort, Response, Markup, g

# @see http://dsnra.jpl.nasa.gov/software/Python/site-packages/Support/libxml2.html


class Node(object):

    def init_with_xpath(self, xpath, site):
        self.site = site
        self.xpath = xpath
        self.state       = self.site.get_xml_by_xpath(self.xpath+'/@state', True)
        self.slug        = self.site.get_xml_by_xpath(self.xpath+'/@slug', True) 
        self.title       = self.site.get_xml_by_xpath(self.xpath+'/title', True)
        self.keywords    = self.site.get_xml_by_xpath(self.xpath+'/keywords', True)
        self.description = self.site.get_xml_by_xpath(self.xpath+'/description', True)
        self.template    = self.site.get_xml_by_xpath(self.xpath+'/template', True)
        self.contentType   = self.site.get_xml_by_xpath(self.xpath+'/content/@type', True)
        self.contentSource = self.site.get_xml_by_xpath(self.xpath+'/content/@source', True)          
        self.content     = None

            
    def get_children(self):
        result = list()
        children = self.site.xml.xpathEval(self.xpath+'/node')
        for c in children:
            n = Node()            
            if '0xbad' == c.prop('state'): continue
            try:
                n.init_with_xpath(self.xpath+'/node[@slug=\''+c.prop('slug')+'\']', self.site)
                result.append(n)                  
            except Exception, e:
                print "Node has no slug and marked as invalid. You can find it by path "+self.xpath+"/node[@status='0xbad']"
                c.setProp('state', '0xbad')  
        return result            


    def get_parent(self):
        if self.xpath == '/site': return None
        tokens = self.xpath.split('/')
        tokens.pop()
        xpath = '/'.join(tokens)
        parent = self.site.get_xml_by_xpath(xpath)
        if parent is None: return None 
        n = Node()
        n.init_with_xpath(xpath, self.site)           
        return n


    def explicit_properties(self):
        self.explicit_property('title')
        self.explicit_property('keywords')
        self.explicit_property('description')
        self.explicit_property('template')
        self.explicit_property('contentType')
        self.explicit_property('contentSource')


    def explicit_property(self, prop):
        value = getattr(self, prop)
        if (value is None or value == ''):
            parent = self.get_parent()
            while (value is None or value == '') and parent is not None:
                value = getattr(parent, prop)
                parent = parent.get_parent()
            setattr(self, prop, value)


    def explicit_content(self):
        print "Explicit content for source=%s & type=%s for node %s" % (self.contentSource, self.contentType, self.xpath)
        
        if self.contentSource is None or self.contentSource == 'inline':     # inline content
            print "Find content inline by xpath="+self.xpath+'/content' 
            self.content = self.site.get_xml_by_xpath(self.xpath+'/content', True)
        elif self.contentSource == 'file': # read from local file
            filename = './data' + self.site.get_xml_by_xpath(self.xpath+'/content', True)
            try:
                self.content = open(filename, 'r').read()  
            except Exception, e:
                self.content = None
                print "Unable to read content from file "+filename
        else: # WTF?
            print "Unknown contentSource=%s on node %s" % (self.contentSource, self.xpath) 

        if self.content is None: 
            print "Content not found"
        else:    
            if self.contentType is None or 'html' == self.contentType: # default case
                pass
            elif 'markdown' == self.contentType or 'md' == self.contentType:
                import markdown2
                self.content = markdown2.markdown(self.content)
            else: # WTF?
                print "Unknown contentType=%s on node %s" % (self.contentType, self.xpath) 


    def __str__(self):
        return "{'slug':'%s', 'state':'%s', 'xpath':'%s', template':'%s', 'title':'%s'}" % (self.slug, self.state, self.xpath, self.template, self.title)



class Site(Node):

    def __init__(self):
        super(Site, self).__init__()
        self.xml = None


    def init_with_xml(self, filename):
        with open(filename, 'r') as f:
            data = f.read()     
        self.xml = libxml2.parseDoc(data) 
        super(Site, self).init_with_xpath('/site', self)


    def validate_tree(self, node, tab):
        tabs = ''
        for i in range(0, tab): tabs += '\t'
        # TODO: debug=true print "%s%s" % (tabs, node)
        children = node.get_children()
        tab += 1
        for c in children:
            self.validate_tree(c, tab)
        tab -= 1 


    def get_node_by_uri(self, uri):
        xpath = '/site/' + '/'.join(map(lambda t: 'node[@slug=\''+t+'\']', uri.split('/')))
        print "Get node by uri=%s -> xpath=%s" % (uri, xpath) 
        n = self.get_node_by_xpath(xpath)
        print "Found %s" % n
        return n         

 
    def get_node_by_xpath(self, xpath, get_content=False):
        n = self.get_xml_by_xpath(xpath, get_content)
        if n is None: return None
        n = Node()
        n.init_with_xpath(xpath, self)
        return n


    def get_xml_by_xpath(self, xpath, get_content=False):
        # print '+-----------%s' % xpath
        nodes = self.xml.xpathEval(xpath)
        if 0 == len(nodes):
            return None
        elif 1 == len(nodes):
            if True == get_content:
                return nodes[0].content
            else:
                return nodes[0]
        else:
            return nodes 



app = Flask(__name__)
site = Site()


@app.route("/")
def index():
    return render_template('index.html', node=site)


@app.route("/<path:path>.html")
def content(path):
    node = site.get_node_by_uri(path)
    if None == node:
        abort(404)

    try:
        node.explicit_properties()
        node.explicit_content()
        return render_template(node.template, node=node)
    except Exception, e:
        if app.debug: 
            raise e
        else: 
            abort(500)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.before_request
def init_site():
    if True: # run always site.xml is None:
        site.init_with_xml("./data/site.xml")
        site.validate_tree(site, 0)     


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8765, debug=True)        



