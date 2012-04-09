#
#   Copyright [2011] [Red Hat, Inc.]
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#  limitations under the License.
#
require 'fileutils'

require 'lib/model/base'

module ConfigServer
  module Model
    class Deployable < Base

      EXCLUDED_DIRS = %w{. ..}

      def self.find(uuid)
        Deployable.new(uuid) if exists?(uuid)
      end

      def self.storage_path(uuid=nil)
        path = uuid ? File.join("deployables", uuid) : "deployables"
        super path
      end

      def self.exists?(uuid)
        File.exists?(storage_path uuid)
      end

      @uuid = nil
      @deployable_dir = nil

      def initialize(uuid)
        super()
        Deployable.ensure_storage_path

        @uuid = uuid
        @deployable_dir = ensure_deployable_dir
        self
      end

      def add_instance(uuid)
        # never actually hold the state of the list of instances
        # always pick up the list from the filesystem
        instance_dir = Instance.storage_path uuid
        if File.directory?(instance_dir)
          FileUtils.ln_s(instance_dir, File.join(@deployable_dir.path, uuid))
        end
        instance_uuids
      end

      def remove_instance(uuid)
        delete_path = File.join(@deployable_dir.path, uuid)
        File.delete(delete_path) if File.exists?(delete_path)
        instance_uuids
      end

      def delete!
        instance_uuids.each do |instance_uuid|
          Instance.delete! instance_uuid
          remove_instance instance_uuid
        end
        FileUtils.rm_rf(@deployable_dir.path)
      end

      def instance_uuids
        @deployable_dir.entries - EXCLUDED_DIRS
      end

      def instances
        @instances ||= instance_uuids.map do |uuid|
          Instance.find(uuid)
        end
      end

      def instances_with_assembly_dependencies(assembly_names)
        if not assembly_names.kind_of? Array
          assembly_names = [assembly_names]
        end
        match_string = "['\"](#{assembly_names.join("|")})['\"]"
        logger.debug("match_string: #{match_string}")
        instance_uuids.select do |uuid|
          p = File.join(@deployable_dir.path, uuid, 'required-parameters.xml')
          File.open(p) do |f|
            not f.grep(/<required-parameter .* assembly=#{match_string}/).empty?
          end if File.exists?(p)
        end
      end

      def registered_timestamp
        File.new(@deployable_dir.path).ctime
      end

      def completed_timestamp
        times = instances.map {|i| i.completed_timestamp }

        # if there are no nils in the instances' completed timestamps
        # find the last (highest) completion timestamp
        # otherwise, nil
        if times.compact == times
          times.max do |t1, t2|
            nilable_max_comparison(t1, t2)
          end
        end
      end

      def status
        states = instances.map {|i| i.status }

        # if all the instances reported a status
        # find the "worst" status (error > incomplete > success)
        # otherwise, at least one instance couldn't report status = "incomplete"
        if states.compact == states
          states.max do |s1, s2|
            # error > incomplete > success
            # which nicely maps to alphabetical order
            nilable_max_comparison(s1, s2)
          end
        else
          "incomplete"
        end
      end

      private
      def nilable_max_comparison(x, y, &block)
        if x and y
          if block_given?
            yield x, y
          else
            x <=> y
          end
        elsif x
          1
        elsif y
          -1
        else
          0
        end
      end

      def ensure_deployable_dir
        path = Deployable.storage_path @uuid
        FileUtils.mkdir_p(path, :mode => 0700) if not File.directory?(path)
        Dir.new(path)
      end
    end
  end
end
