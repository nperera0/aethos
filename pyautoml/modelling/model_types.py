class ModelBase(object):

    def __init__(self, model_object):

        self.data = model_object._data_properties.data
        self.train_data = model_object._data_properties.train_data
        self.test_data = model_object._data_properties.train_data

class TextModel(ModelBase):

    def __init__(self, model_object):

        super().__init__(model_object)

class ClusterModel(ModelBase):

    def __init__(self, model_object):

        super().__init__(self, model_object)

    def filter_cluster(self, col: str, cluster_no: int):
        """
        Filters data by a cluster number for analysis.
        
        Parameters
        ----------
        col : str
            Column of cluster labels
        cluster_no : int
            Cluster number to filter by
        
        Returns
        -------
        Dataframe
            Filtered data or test dataframe
        """

        if self.data is not None:
            return self.data[self.data[col] == cluster_no]
        else:
            return self.test_data[self.test_data[col] == cluster_no]