export namespace main {
	
	export class FileData {
	    name: string;
	    data: string;
	    path: string;
	
	    static createFrom(source: any = {}) {
	        return new FileData(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.name = source["name"];
	        this.data = source["data"];
	        this.path = source["path"];
	    }
	}

}

