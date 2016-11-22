import itertools
import os
import sys
sys.path.insert(0, '.')
import tarfile
import yaml

from microdrop_utility import Version
import path_helpers as ph


# create a version sting based on the git revision/branch
version = str(Version.from_git_repository())

package_name = 'base_node_plugin_template'
plugin_name = 'wheelerlab.base_node_plugin_template'

package_dir = ph.path(__file__).realpath().parent


if __name__ == '__main__':
    current_dir = ph.path(os.getcwd())
    os.chdir(package_dir)

    try:
        # Create the tar.gz plugin archive
        tar_path = current_dir.joinpath("%s-%s.tar.gz" % (package_name,
                                                          version))
        with tarfile.open(tar_path, "w:gz") as tar:
            # write the 'properties.yml' file
            properties = {'plugin_name': plugin_name, 'package_name':
                          package_name, 'version': version}

            properties_path = package_dir.joinpath('properties.yml')
            with properties_path.open('w') as f:
                f.write(yaml.dump(properties))
                print 'Wrote: {}'.format(properties_path)


            here = ph.path('.')
            for path_i in itertools.chain(here.files('*.py'),
                                          map(ph.path, ['properties.yml',
                                                        'hooks',
                                                        'requirements.txt'])):
                if path_i.exists():
                    tar.add(str(here.relpathto(path_i)))
            print 'Wrote: {}'.format(current_dir.relpathto(tar_path))
    finally:
        os.chdir(current_dir)
